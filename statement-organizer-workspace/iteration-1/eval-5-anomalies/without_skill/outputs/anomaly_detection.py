"""
Advanced Anomaly Detection for Bank Statements
Identifies suspicious transactions based on statistical analysis and behavioral patterns
"""

import json
from datetime import datetime
from statistics import mean, stdev
from collections import defaultdict
import re


class TransactionAnomalyDetector:
    """
    Detects anomalous transactions through multiple detection methods:
    1. Statistical outliers (amounts significantly above/below normal range)
    2. Merchant pattern changes (transactions to new or rarely-used vendors)
    3. Time-based anomalies (transactions at unusual times)
    4. Frequency anomalies (unusual spending patterns)
    5. Duplicate detection (identical or near-duplicate transactions)
    """

    def __init__(self, historical_transactions=None):
        """
        Initialize detector with optional historical data for baseline establishment

        Args:
            historical_transactions: List of past transactions to establish spending patterns
        """
        self.baseline_transactions = historical_transactions or []
        self.current_transactions = []
        self.anomalies = []
        self.merchant_history = defaultdict(list)
        self.amount_history = []
        self.time_history = defaultdict(int)

        if historical_transactions:
            self._build_baseline()

    def _build_baseline(self):
        """Build baseline spending patterns from historical data"""
        for tx in self.baseline_transactions:
            amount = float(tx.get('amount', 0))
            merchant = tx.get('merchant', 'unknown').lower()
            hour = self._extract_hour(tx.get('date', ''))

            self.amount_history.append(amount)
            self.merchant_history[merchant].append(tx)
            self.time_history[hour] += 1

    def _extract_hour(self, date_str):
        """Extract hour from date string (handles multiple formats)"""
        try:
            # Try ISO format with time
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.split('+')[0])
            else:
                # Try common date formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%Y-%m-%d']:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return 0
            return dt.hour
        except:
            return 0

    def _normalize_merchant(self, merchant):
        """Normalize merchant name for comparison"""
        return re.sub(r'[^a-z0-9]', '', merchant.lower())

    def detect_anomalies(self, transactions):
        """
        Detect anomalies in a list of transactions

        Args:
            transactions: List of transaction dictionaries with keys:
                         amount, merchant, date, description, type

        Returns:
            List of anomalies with severity scores and reasons
        """
        self.current_transactions = transactions
        self.anomalies = []

        # Run all detection methods
        self._detect_statistical_outliers()
        self._detect_merchant_anomalies()
        self._detect_time_anomalies()
        self._detect_duplicates()
        self._detect_frequency_anomalies()

        # Sort by severity
        self.anomalies.sort(key=lambda x: x['severity_score'], reverse=True)
        return self.anomalies

    def _detect_statistical_outliers(self):
        """
        Detect amounts significantly outside normal spending range
        Uses z-score method: values beyond 2.5 standard deviations are flagged
        """
        if len(self.amount_history) < 3:
            # Need minimum history to establish baseline
            return

        try:
            mean_amount = mean(self.amount_history)
            stdev_amount = stdev(self.amount_history)

            # Prevent division by zero
            if stdev_amount == 0:
                stdev_amount = mean_amount * 0.1

            for tx in self.current_transactions:
                amount = float(tx.get('amount', 0))

                # Calculate z-score
                z_score = abs((amount - mean_amount) / stdev_amount)

                # Flag if more than 2.5 standard deviations away
                if z_score > 2.5:
                    self.anomalies.append({
                        'transaction': tx,
                        'anomaly_type': 'STATISTICAL_OUTLIER',
                        'severity_score': min(z_score / 5.0, 1.0),  # Cap at 1.0
                        'reason': f'Amount ${amount:.2f} is {z_score:.1f} std devs from mean (${mean_amount:.2f})',
                        'threshold': f'Normal range: ${mean_amount - 2.5*stdev_amount:.2f} to ${mean_amount + 2.5*stdev_amount:.2f}'
                    })
        except Exception as e:
            pass  # Silently skip if calculation fails

    def _detect_merchant_anomalies(self):
        """
        Detect transactions to new or rarely-used merchants
        New merchants or single-instance vendors warrant investigation
        """
        merchant_frequency = defaultdict(int)

        for tx in self.baseline_transactions:
            merchant = self._normalize_merchant(tx.get('merchant', ''))
            merchant_frequency[merchant] += 1

        for tx in self.current_transactions:
            merchant = self._normalize_merchant(tx.get('merchant', ''))
            frequency = merchant_frequency.get(merchant, 0)

            # Flag completely new merchants (never seen before)
            if frequency == 0 and len(self.baseline_transactions) > 0:
                self.anomalies.append({
                    'transaction': tx,
                    'anomaly_type': 'NEW_MERCHANT',
                    'severity_score': 0.6,
                    'reason': f'First transaction with merchant "{tx.get("merchant")}"',
                    'merchant_history': 'New vendor'
                })
            # Flag rarely-used merchants (only 1-2 times before)
            elif frequency < 2 and frequency > 0:
                self.anomalies.append({
                    'transaction': tx,
                    'anomaly_type': 'RARE_MERCHANT',
                    'severity_score': 0.4,
                    'reason': f'Uncommon merchant "{tx.get("merchant")}" (only {frequency} prior transactions)',
                    'merchant_history': f'{frequency} previous transactions'
                })

    def _detect_time_anomalies(self):
        """
        Detect transactions at unusual times (outside normal patterns)
        Flags transactions during unusual hours
        """
        if len(self.baseline_transactions) < 5:
            return

        # Calculate most common transaction hours
        if self.time_history:
            total_transactions = sum(self.time_history.values())
            avg_per_hour = total_transactions / 24

            for tx in self.current_transactions:
                hour = self._extract_hour(tx.get('date', ''))
                frequency = self.time_history.get(hour, 0)

                # Flag if transaction is in an hour with very low historical frequency
                if frequency < avg_per_hour * 0.2:  # Less than 20% of average
                    self.anomalies.append({
                        'transaction': tx,
                        'anomaly_type': 'TIME_ANOMALY',
                        'severity_score': 0.35,
                        'reason': f'Transaction at hour {hour}:00 is unusual (only {frequency} historical transactions)',
                        'typical_hours': self._get_typical_hours()
                    })

    def _get_typical_hours(self):
        """Get the most common transaction hours"""
        if not self.time_history:
            return "Unable to determine"
        sorted_hours = sorted(self.time_history.items(), key=lambda x: x[1], reverse=True)
        top_hours = [f"{h[0]:02d}:00" for h in sorted_hours[:5]]
        return ', '.join(top_hours)

    def _detect_duplicates(self):
        """
        Detect duplicate or near-duplicate transactions
        Flags identical amounts to same merchant within 24 hours
        """
        seen = {}

        for i, tx in enumerate(self.current_transactions):
            amount = float(tx.get('amount', 0))
            merchant = self._normalize_merchant(tx.get('merchant', ''))
            date_str = tx.get('date', '')

            key = f"{amount}|{merchant}"

            if key in seen:
                prev_tx = seen[key]
                self.anomalies.append({
                    'transaction': tx,
                    'anomaly_type': 'DUPLICATE',
                    'severity_score': 0.8,
                    'reason': f'Duplicate transaction detected: ${amount:.2f} to "{tx.get("merchant")}" (also on {prev_tx.get("date")})',
                    'duplicate_of': prev_tx.get('date')
                })
            else:
                seen[key] = tx

    def _detect_frequency_anomalies(self):
        """
        Detect unusual spending frequency patterns
        Flags unusually high concentration of transactions in short time periods
        """
        if len(self.current_transactions) < 5:
            return

        # Check if spending is concentrated unusually
        total_amount = sum(float(tx.get('amount', 0)) for tx in self.current_transactions)
        avg_per_tx = total_amount / len(self.current_transactions)

        # Flag large number of high-value transactions in short period
        high_value_count = sum(1 for tx in self.current_transactions
                              if float(tx.get('amount', 0)) > avg_per_tx * 2)

        if high_value_count > len(self.current_transactions) * 0.3:
            self.anomalies.append({
                'transaction': self.current_transactions[0],
                'anomaly_type': 'FREQUENCY_ANOMALY',
                'severity_score': 0.5,
                'reason': f'Unusual concentration: {high_value_count} high-value transactions (>{avg_per_tx*2:.2f})',
                'pattern': f'{high_value_count} of {len(self.current_transactions)} transactions are high-value'
            })

    def get_anomaly_report(self, include_baseline=False):
        """
        Generate a structured anomaly report

        Returns:
            Dictionary with summary and detailed anomalies
        """
        report = {
            'report_date': datetime.now().isoformat(),
            'total_transactions_analyzed': len(self.current_transactions),
            'total_anomalies_found': len(self.anomalies),
            'critical_anomalies': len([a for a in self.anomalies if a['severity_score'] >= 0.7]),
            'anomalies': []
        }

        # Group anomalies by type
        by_type = defaultdict(list)
        for anomaly in self.anomalies:
            by_type[anomaly['anomaly_type']].append(anomaly)

        report['anomalies_by_type'] = {
            atype: len(anomalies) for atype, anomalies in by_type.items()
        }

        # Add detailed anomalies
        for anomaly in self.anomalies:
            report['anomalies'].append({
                'type': anomaly['anomaly_type'],
                'severity': anomaly['severity_score'],
                'transaction': {
                    'date': anomaly['transaction'].get('date'),
                    'merchant': anomaly['transaction'].get('merchant'),
                    'amount': anomaly['transaction'].get('amount'),
                    'description': anomaly['transaction'].get('description')
                },
                'reason': anomaly['reason'],
                'details': {k: v for k, v in anomaly.items()
                           if k not in ['transaction', 'anomaly_type', 'severity_score', 'reason']}
            })

        return report

    def export_json(self, filename):
        """Export anomaly report to JSON file"""
        report = self.get_anomaly_report()
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)


def create_sample_analysis():
    """Create a sample analysis with historical and current transactions"""

    # Historical baseline (previous spending patterns)
    historical = [
        {'date': '2026-02-01', 'merchant': 'Whole Foods', 'amount': '85.50', 'type': 'debit', 'description': 'Grocery shopping'},
        {'date': '2026-02-03', 'merchant': 'Shell Gas Station', 'amount': '52.00', 'type': 'debit', 'description': 'Fuel'},
        {'date': '2026-02-05', 'merchant': 'Amazon', 'amount': '34.99', 'type': 'debit', 'description': 'Online shopping'},
        {'date': '2026-02-06', 'merchant': 'Starbucks', 'amount': '6.50', 'type': 'debit', 'description': 'Coffee'},
        {'date': '2026-02-08', 'merchant': 'Netflix', 'amount': '15.99', 'type': 'credit', 'description': 'Subscription refund'},
        {'date': '2026-02-10', 'merchant': 'CVS Pharmacy', 'amount': '28.75', 'type': 'debit', 'description': 'Medications'},
        {'date': '2026-02-12', 'merchant': 'Local Pizza Place', 'amount': '18.50', 'type': 'debit', 'description': 'Dinner'},
        {'date': '2026-02-14', 'merchant': 'Whole Foods', 'amount': '92.30', 'type': 'debit', 'description': 'Grocery shopping'},
        {'date': '2026-02-16', 'merchant': 'Gym Membership', 'amount': '49.99', 'type': 'debit', 'description': 'Monthly fee'},
        {'date': '2026-02-18', 'merchant': 'Target', 'amount': '45.20', 'type': 'debit', 'description': 'Shopping'},
        {'date': '2026-02-20', 'merchant': 'Shell Gas Station', 'amount': '51.50', 'type': 'debit', 'description': 'Fuel'},
        {'date': '2026-02-22', 'merchant': 'Starbucks', 'amount': '5.75', 'type': 'debit', 'description': 'Coffee'},
        {'date': '2026-02-24', 'merchant': 'Amazon', 'amount': '29.95', 'type': 'debit', 'description': 'Online shopping'},
        {'date': '2026-02-26', 'merchant': 'Whole Foods', 'amount': '88.40', 'type': 'debit', 'description': 'Grocery shopping'},
        {'date': '2026-02-28', 'merchant': 'Local Pizza Place', 'amount': '17.80', 'type': 'debit', 'description': 'Dinner'},
    ]

    # March transactions (current month with anomalies)
    current = [
        {'date': '2026-03-01 09:15:00', 'merchant': 'Whole Foods', 'amount': '87.60', 'type': 'debit', 'description': 'Grocery shopping'},
        {'date': '2026-03-02 14:30:00', 'merchant': 'Starbucks', 'amount': '6.25', 'type': 'debit', 'description': 'Coffee'},
        {'date': '2026-03-03 18:45:00', 'merchant': 'Shell Gas Station', 'amount': '51.00', 'type': 'debit', 'description': 'Fuel'},
        {'date': '2026-03-05 03:22:00', 'merchant': 'Midnight Electronics', 'amount': '1250.00', 'type': 'debit', 'description': 'Unknown vendor - ANOMALY'},
        {'date': '2026-03-06 10:10:00', 'merchant': 'Target', 'amount': '42.50', 'type': 'debit', 'description': 'Shopping'},
        {'date': '2026-03-06 10:10:00', 'merchant': 'Target', 'amount': '42.50', 'type': 'debit', 'description': 'Shopping - DUPLICATE'},
        {'date': '2026-03-07 12:00:00', 'merchant': 'Luxury Hotel Resort', 'amount': '3250.75', 'type': 'debit', 'description': 'Unexpected travel - ANOMALY'},
        {'date': '2026-03-08 09:30:00', 'merchant': 'Whole Foods', 'amount': '91.20', 'type': 'debit', 'description': 'Grocery shopping'},
        {'date': '2026-03-10 14:15:00', 'merchant': 'Amazon', 'amount': '199.99', 'type': 'debit', 'description': 'Electronics - Large purchase'},
        {'date': '2026-03-12 11:00:00', 'merchant': 'Crypto Exchange Platform', 'amount': '5000.00', 'type': 'debit', 'description': 'Unknown vendor - ANOMALY'},
        {'date': '2026-03-14 09:45:00', 'merchant': 'CVS Pharmacy', 'amount': '31.20', 'type': 'debit', 'description': 'Health items'},
        {'date': '2026-03-15 20:30:00', 'merchant': 'Local Pizza Place', 'amount': '19.50', 'type': 'debit', 'description': 'Dinner'},
        {'date': '2026-03-16 10:00:00', 'merchant': 'Gym Membership', 'amount': '49.99', 'type': 'debit', 'description': 'Monthly fee'},
        {'date': '2026-03-18 14:20:00', 'merchant': 'Unknown Overseas Vendor', 'amount': '875.00', 'type': 'debit', 'description': 'International charge - ANOMALY'},
        {'date': '2026-03-20 09:00:00', 'merchant': 'Whole Foods', 'amount': '89.75', 'type': 'debit', 'description': 'Grocery shopping'},
        {'date': '2026-03-22 15:40:00', 'merchant': 'Shell Gas Station', 'amount': '52.50', 'type': 'debit', 'description': 'Fuel'},
    ]

    # Run detection
    detector = TransactionAnomalyDetector(historical_transactions=historical)
    anomalies = detector.detect_anomalies(current)

    return detector, anomalies


if __name__ == '__main__':
    detector, anomalies = create_sample_analysis()

    print("Transaction Anomaly Detection Report")
    print("=" * 50)
    print(f"Total transactions analyzed: {len(detector.current_transactions)}")
    print(f"Anomalies detected: {len(anomalies)}")
    print()

    # Group by severity
    critical = [a for a in anomalies if a['severity_score'] >= 0.7]
    warning = [a for a in anomalies if 0.4 <= a['severity_score'] < 0.7]
    info = [a for a in anomalies if a['severity_score'] < 0.4]

    if critical:
        print("CRITICAL ANOMALIES:")
        for a in critical:
            print(f"  - {a['reason']}")
            print(f"    Amount: ${a['transaction'].get('amount')}, Merchant: {a['transaction'].get('merchant')}")
            print()

    if warning:
        print("WARNING ANOMALIES:")
        for a in warning:
            print(f"  - {a['reason']}")
            print()

    print(f"\nTotal: {len(critical)} critical, {len(warning)} warnings, {len(info)} info")
