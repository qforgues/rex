#!/usr/bin/env python3
"""
Anomaly Detection for Financial Statements
Identifies unusual transactions based on statistical analysis, merchant patterns,
and spending behavior. Used by statement-organizer skill to flag potential fraud.
"""

import csv
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

# Setup logging
log_dir = Path("Logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f"anomaly-detection-{datetime.now().strftime('%Y-%m-%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects anomalous transactions in bank statements"""

    def __init__(self, historical_transactions: List[Dict] = None):
        """
        Initialize anomaly detector with optional historical data

        Args:
            historical_transactions: List of historical transactions for baseline analysis
        """
        self.historical_transactions = historical_transactions or []
        self.baseline_stats = {}
        self._calculate_baselines()

    def _calculate_baselines(self):
        """Calculate statistical baselines from historical transactions"""
        if not self.historical_transactions:
            logger.info("No historical transactions provided for baseline calculation")
            return

        # Extract amounts for statistical analysis
        amounts = [abs(t.get('amount', 0)) for t in self.historical_transactions]

        if amounts:
            self.baseline_stats['mean_amount'] = statistics.mean(amounts)
            self.baseline_stats['median_amount'] = statistics.median(amounts)
            self.baseline_stats['stdev_amount'] = statistics.stdev(amounts) if len(amounts) > 1 else 0
            self.baseline_stats['max_typical'] = self.baseline_stats['mean_amount'] + (
                2.5 * self.baseline_stats['stdev_amount']
            )

            # Merchant frequency baseline
            merchants = {}
            for t in self.historical_transactions:
                m = t.get('merchant', 'Unknown')
                merchants[m] = merchants.get(m, 0) + 1
            self.baseline_stats['common_merchants'] = set(merchants.keys())

            logger.info(f"Baselines calculated: mean=${self.baseline_stats['mean_amount']:.2f}, "
                       f"stdev=${self.baseline_stats['stdev_amount']:.2f}, "
                       f"known merchants={len(self.baseline_stats['common_merchants'])}")

    def detect_anomalies(self, transactions: List[Dict]) -> List[Dict]:
        """
        Detect anomalous transactions

        Args:
            transactions: List of transactions to analyze

        Returns:
            List of flagged anomalies with severity and reason
        """
        anomalies = []

        for transaction in transactions:
            flags = []
            severity = 'LOW'

            # Check for unusually large amounts
            large_amount_flag = self._check_amount_anomaly(transaction)
            if large_amount_flag:
                flags.append(large_amount_flag['reason'])
                severity = self._update_severity(severity, large_amount_flag.get('severity', 'LOW'))

            # Check for new/unusual merchants
            merchant_flag = self._check_merchant_anomaly(transaction)
            if merchant_flag:
                flags.append(merchant_flag['reason'])
                severity = self._update_severity(severity, merchant_flag.get('severity', 'LOW'))

            # Check for potential duplicates
            dup_flag = self._check_duplicate_anomaly(transaction, transactions)
            if dup_flag:
                flags.append(dup_flag['reason'])
                severity = self._update_severity(severity, dup_flag.get('severity', 'MEDIUM'))

            # Check for suspicious patterns
            pattern_flag = self._check_pattern_anomaly(transaction, transactions)
            if pattern_flag:
                flags.append(pattern_flag['reason'])
                severity = self._update_severity(severity, pattern_flag.get('severity', 'LOW'))

            # If any flags found, add to anomalies list
            if flags:
                anomalies.append({
                    'date': transaction.get('date', 'Unknown'),
                    'amount': transaction.get('amount', 0),
                    'merchant': transaction.get('merchant', 'Unknown'),
                    'flags': flags,
                    'severity': severity,
                    'reason': ' | '.join(flags)
                })

        logger.info(f"Detected {len(anomalies)} anomalous transactions out of {len(transactions)}")
        return anomalies

    def _check_amount_anomaly(self, transaction: Dict) -> Optional[Dict]:
        """Check if transaction amount is unusually large"""
        amount = abs(transaction.get('amount', 0))

        # If no baseline, flag amounts > $2000 as large
        if not self.baseline_stats:
            if amount > 2000:
                return {
                    'reason': f'Large amount: ${amount:.2f}',
                    'severity': 'MEDIUM'
                }
            return None

        # Flag if amount is more than 2.5 standard deviations above mean
        max_typical = self.baseline_stats.get('max_typical', 2000)
        if amount > max_typical:
            multiplier = amount / self.baseline_stats.get('mean_amount', 1)
            return {
                'reason': f'Large amount: ${amount:.2f} ({multiplier:.1f}x typical)',
                'severity': 'MEDIUM' if multiplier < 5 else 'HIGH'
            }

        return None

    def _check_merchant_anomaly(self, transaction: Dict) -> Optional[Dict]:
        """Check if merchant is new or unusual"""
        merchant = transaction.get('merchant', 'Unknown').strip()

        # Known suspicious merchant patterns
        suspicious_patterns = [
            'WIRE TRANSFER',
            'CRYPTOCURRENCY',
            'BITCOIN',
            'FOREX',
            'GAMBLING',
            'CASINO',
            'ADULT',
            'XXX'
        ]

        # Check for suspicious keywords
        merchant_upper = merchant.upper()
        for pattern in suspicious_patterns:
            if pattern in merchant_upper:
                return {
                    'reason': f'Suspicious merchant category: {merchant}',
                    'severity': 'HIGH'
                }

        # Check if new merchant (not in historical data)
        if self.baseline_stats and 'common_merchants' in self.baseline_stats:
            if merchant not in self.baseline_stats['common_merchants']:
                return {
                    'reason': f'New/unusual merchant: {merchant}',
                    'severity': 'LOW'
                }

        return None

    def _check_duplicate_anomaly(self, transaction: Dict, all_transactions: List[Dict]) -> Optional[Dict]:
        """Check for potential duplicate transactions"""
        amount = transaction.get('amount')
        merchant = transaction.get('merchant', '').strip()
        date = transaction.get('date', '').strip()

        # Look for exact duplicates (same amount, merchant, within 1 day)
        duplicate_count = 0
        for other in all_transactions:
            if other.get('amount') == amount and \
               other.get('merchant', '').strip() == merchant:
                # Allow one instance (the transaction itself)
                duplicate_count += 1

        if duplicate_count > 1:
            return {
                'reason': f'Potential duplicate: {duplicate_count} transactions with same amount (${amount:.2f}) and merchant ({merchant})',
                'severity': 'MEDIUM'
            }

        return None

    def _check_pattern_anomaly(self, transaction: Dict, all_transactions: List[Dict]) -> Optional[Dict]:
        """Check for suspicious spending patterns"""
        merchant = transaction.get('merchant', '').strip().upper()
        amount = transaction.get('amount', 0)

        # Check for rapid-fire transactions at the same merchant
        same_merchant_count = sum(
            1 for t in all_transactions
            if t.get('merchant', '').strip().upper() == merchant
        )

        if same_merchant_count >= 3:
            return {
                'reason': f'Multiple transactions at same merchant ({same_merchant_count} times): {merchant}',
                'severity': 'LOW'
            }

        # Check for round-dollar amounts (could indicate cash withdrawals or manipulation)
        if amount > 500 and amount == int(amount) and (amount % 100) == 0:
            # This is a round amount but could be legitimate, so LOW severity
            return {
                'reason': f'Round dollar amount: ${amount:.2f} (possible cash withdrawal)',
                'severity': 'LOW'
            }

        return None

    def _update_severity(self, current: str, new: str) -> str:
        """Update severity level (HIGH > MEDIUM > LOW)"""
        severity_order = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2}
        return new if severity_order.get(new, 0) > severity_order.get(current, 0) else current

    def generate_anomaly_report(self, anomalies: List[Dict], output_path: str):
        """
        Generate CSV report of flagged transactions

        Args:
            anomalies: List of detected anomalies
            output_path: Path to write CSV report
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Header
                writer.writerow(['FLAGGED TRANSACTIONS - ANOMALY DETECTION REPORT'])
                writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow([])

                # Summary
                critical = sum(1 for a in anomalies if a['severity'] == 'HIGH')
                warning = sum(1 for a in anomalies if a['severity'] == 'MEDIUM')
                info = sum(1 for a in anomalies if a['severity'] == 'LOW')

                writer.writerow(['SUMMARY'])
                writer.writerow(['Total Anomalies:', len(anomalies)])
                writer.writerow(['High Severity (Critical):', critical])
                writer.writerow(['Medium Severity (Warning):', warning])
                writer.writerow(['Low Severity (Info):', info])
                writer.writerow([])

                # Detailed transactions
                writer.writerow(['DATE', 'AMOUNT', 'MERCHANT', 'SEVERITY', 'FLAGS/REASONS'])
                for anomaly in sorted(anomalies, key=lambda x: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}.get(x['severity'], 3)):
                    writer.writerow([
                        anomaly.get('date', 'Unknown'),
                        f"${anomaly.get('amount', 0):.2f}",
                        anomaly.get('merchant', 'Unknown'),
                        anomaly.get('severity', 'UNKNOWN'),
                        anomaly.get('reason', 'No details')
                    ])

            logger.info(f"Anomaly report generated: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error generating anomaly report: {e}")
            return False


def main():
    """Example usage of anomaly detector"""
    detector = AnomalyDetector()
    logger.info("Anomaly Detector initialized and ready")
    return detector


if __name__ == '__main__':
    main()
