# Bank Statement Anomaly Detection - Usage Guide

## Quick Start

### Installation & Setup

```python
# Copy the anomaly_detection.py file to your project

# No external dependencies required beyond Python stdlib:
import json
import datetime
import statistics
import collections
import re
```

### Basic Usage (5 Minutes)

```python
from anomaly_detection import TransactionAnomalyDetector, create_sample_analysis

# Option 1: Use included sample data
detector, anomalies = create_sample_analysis()

# Option 2: Use your own data
historical = [
    {'date': '2026-02-01', 'merchant': 'Whole Foods', 'amount': '85.50', 'type': 'debit'},
    {'date': '2026-02-03', 'merchant': 'Shell Gas', 'amount': '52.00', 'type': 'debit'},
    # ... more historical transactions
]

current = [
    {'date': '2026-03-01', 'merchant': 'Whole Foods', 'amount': '87.60', 'type': 'debit'},
    {'date': '2026-03-05', 'merchant': 'Unknown Vendor', 'amount': '5000.00', 'type': 'debit'},
    # ... current month transactions
]

detector = TransactionAnomalyDetector(historical_transactions=historical)
anomalies = detector.detect_anomalies(current)

# View results
for anomaly in anomalies:
    print(f"Type: {anomaly['anomaly_type']}")
    print(f"Reason: {anomaly['reason']}")
    print(f"Severity: {anomaly['severity_score']}")
```

---

## Detailed Workflow

### Step 1: Prepare Your Data

#### From Bank CSV
```python
import csv

def load_csv_statement(filename):
    """Load transactions from CSV file"""
    transactions = []
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append({
                'date': row['Date'],
                'merchant': row['Merchant/Vendor'],
                'amount': row['Amount'],
                'type': row['Type'],  # 'debit' or 'credit'
                'description': row.get('Description', '')
            })
    return transactions

# Load your statements
feb_statement = load_csv_statement('dart_bank_feb_2026.csv')
march_statement = load_csv_statement('dart_bank_march_2026.csv')
```

#### From Bank API
```python
def load_from_bank_api(account_id, start_date, end_date):
    """Example: Load from banking API"""
    import requests

    response = requests.get(
        'https://api.dartbank.com/transactions',
        params={
            'account_id': account_id,
            'start_date': start_date,
            'end_date': end_date,
        },
        headers={'Authorization': f'Bearer {API_KEY}'}
    )

    return response.json()['transactions']

# Load your data
march_data = load_from_bank_api('ACC123456', '2026-03-01', '2026-03-31')
```

#### Manual Entry
```python
# If importing from Excel or manual entry
transactions = [
    {
        'date': '2026-03-01 09:15:00',
        'merchant': 'Whole Foods Market',
        'amount': '87.60',
        'type': 'debit',
        'description': 'Groceries'
    },
    # ... more entries
]
```

### Step 2: Initialize Detector

```python
from anomaly_detection import TransactionAnomalyDetector

# Method 1: With historical baseline (recommended)
detector = TransactionAnomalyDetector(
    historical_transactions=feb_statement
)

# Method 2: Without baseline (limited effectiveness)
detector = TransactionAnomalyDetector()
```

### Step 3: Run Detection

```python
# Analyze current month transactions
anomalies = detector.detect_anomalies(march_statement)

# Results are sorted by severity (highest first)
print(f"Found {len(anomalies)} anomalies")
```

### Step 4: Review Results

```python
# Method 1: Print to console
for anomaly in anomalies:
    if anomaly['severity_score'] >= 0.7:  # Critical only
        print(f"CRITICAL: {anomaly['reason']}")
        print(f"  Merchant: {anomaly['transaction']['merchant']}")
        print(f"  Amount: ${anomaly['transaction']['amount']}")
        print()

# Method 2: Generate report
report = detector.get_anomaly_report()
print(f"Critical anomalies: {report['critical_anomalies']}")
print(f"Total anomalies: {report['total_anomalies_found']}")

# Method 3: Export to file
detector.export_json('march_2026_anomalies.json')
```

### Step 5: Take Action

```python
# For each critical anomaly:
critical = [a for a in anomalies if a['severity_score'] >= 0.7]

for anomaly in critical:
    tx = anomaly['transaction']

    # Decision tree:
    if anomaly['anomaly_type'] == 'DUPLICATE':
        # Action: Contact merchant to confirm/reverse duplicate
        print(f"DUPLICATE: Contact {tx['merchant']} about {tx['amount']}")

    elif anomaly['anomaly_type'] == 'STATISTICAL_OUTLIER':
        # Action: Verify large charges
        print(f"LARGE CHARGE: Did you authorize {tx['amount']} at {tx['merchant']}?")

    elif anomaly['anomaly_type'] == 'NEW_MERCHANT':
        # Action: Verify unfamiliar vendor
        print(f"NEW VENDOR: Verify charge to {tx['merchant']}")

    elif anomaly['anomaly_type'] == 'TIME_ANOMALY':
        # Action: Suspicious timing
        print(f"UNUSUAL TIME: Charge at {tx['date']} to {tx['merchant']}")
```

---

## Integration Examples

### Integration with Banking App

```python
# Flask web app example
from flask import Flask, jsonify
from anomaly_detection import TransactionAnomalyDetector

app = Flask(__name__)

@app.route('/api/analyze-statement', methods=['POST'])
def analyze_statement():
    """API endpoint for anomaly detection"""
    data = request.json

    # Initialize detector
    detector = TransactionAnomalyDetector(
        historical_transactions=data['historical']
    )

    # Run analysis
    anomalies = detector.detect_anomalies(data['current'])

    # Return report
    return jsonify(detector.get_anomaly_report())

@app.route('/api/dispute/<anomaly_id>', methods=['POST'])
def dispute_transaction(anomaly_id):
    """File dispute for flagged transaction"""
    # Contact bank API to dispute
    # Send notification to user
    return jsonify({'status': 'dispute_filed'})
```

### Integration with Email Alerts

```python
import smtplib
from email.mime.text import MIMEText

def send_fraud_alert(anomalies):
    """Send email alert for critical anomalies"""
    critical = [a for a in anomalies if a['severity_score'] >= 0.7]

    if not critical:
        return

    subject = f"Alert: {len(critical)} Suspicious Transaction(s) Detected"

    body = "Critical anomalies detected in your Dart Bank statement:\n\n"
    for a in critical:
        body += f"• {a['transaction']['merchant']}: ${a['transaction']['amount']}\n"
        body += f"  Reason: {a['reason']}\n\n"

    # Send via SMTP
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = 'alerts@dartbank.com'
    msg['To'] = 'customer@email.com'

    server = smtplib.SMTP('smtp.dartbank.com')
    server.send_message(msg)
    server.quit()
```

### Scheduled Monthly Analysis

```python
import schedule
import time
from datetime import datetime

def monthly_statement_analysis():
    """Run automatically on the 1st of each month"""
    now = datetime.now()

    # Load previous month as baseline
    prev_month = (now.month - 2) % 12 + 1
    baseline = load_csv_statement(f'statement_{prev_month:02d}.csv')

    # Load current month
    current = load_csv_statement(f'statement_{now.month:02d}.csv')

    # Analyze
    detector = TransactionAnomalyDetector(baseline)
    anomalies = detector.detect_anomalies(current)

    # Report
    detector.export_json(f'anomalies_{now.month:02d}.json')
    send_fraud_alert(anomalies)

# Schedule it
schedule.every().month.do(monthly_statement_analysis)

# Run scheduler
while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## Real-World Scenarios

### Scenario 1: Detect Credit Card Fraud

```python
# Load statements from potentially compromised card
detector = TransactionAnomalyDetector(
    historical_transactions=load_csv_statement('jan_2026.csv')
)

feb = load_csv_statement('feb_2026.csv')
anomalies = detector.detect_anomalies(feb)

# Check for fraud pattern
fraud_indicators = {
    'multiple_new_merchants': len([a for a in anomalies
                                   if a['anomaly_type'] == 'NEW_MERCHANT']) > 3,
    'multiple_high_amounts': len([a for a in anomalies
                                  if a['anomaly_type'] == 'STATISTICAL_OUTLIER']) > 2,
    'international_charges': any('overseas' in a['transaction']['merchant'].lower()
                                for a in anomalies)
}

if sum(fraud_indicators.values()) >= 2:
    # High probability of account compromise
    print("FRAUD ALERT: Likely account takeover detected")
    print("RECOMMENDED ACTION: Cancel card and contact bank immediately")
```

### Scenario 2: Monitor Business Account

```python
# Different threshold for business with varied spending
detector = TransactionAnomalyDetector(
    historical_transactions=load_csv_statement('last_quarter.csv')
)

# Analyze current month
this_month = load_csv_statement('current.csv')
anomalies = detector.detect_anomalies(this_month)

# Business rule: Flag only >$5000 or international charges
business_alerts = [a for a in anomalies
                   if float(a['transaction']['amount']) > 5000
                   or 'international' in a['reason'].lower()]

for alert in business_alerts:
    # Send to accounting for approval
    notify_accounting(alert)
```

### Scenario 3: Identity Theft Prevention

```python
# Collect 6 months of baseline
historical = []
for month in range(1, 7):
    historical.extend(load_csv_statement(f'statement_2025_{month:02d}.csv'))

# Monitor for sudden changes
detector = TransactionAnomalyDetector(historical_transactions=historical)

# Analyze current month
anomalies = detector.detect_anomalies(load_csv_statement('current.csv'))

# Check for identity theft pattern
identity_theft_risk = {
    'new_merchants_count': len([a for a in anomalies
                               if a['anomaly_type'] == 'NEW_MERCHANT']),
    'total_amount': sum(float(a['transaction']['amount'])
                       for a in anomalies),
    'unusual_hours': len([a for a in anomalies
                         if a['anomaly_type'] == 'TIME_ANOMALY'])
}

if (identity_theft_risk['new_merchants_count'] > 5 and
    identity_theft_risk['total_amount'] > 10000):
    # Likely identity theft
    print("HIGH RISK: Possible identity theft detected")
    print(f"- {identity_theft_risk['new_merchants_count']} new merchants")
    print(f"- ${identity_theft_risk['total_amount']:.2f} in suspicious charges")
```

---

## Customization & Tuning

### Adjust Detection Thresholds

```python
class CustomAnomalyDetector(TransactionAnomalyDetector):
    """Customize detection parameters"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Adjust thresholds
        self.z_score_threshold = 2.0  # More sensitive (default 2.5)
        self.new_merchant_severity = 0.7  # More serious (default 0.6)
        self.min_frequency_new = 3  # Need 3+ uses to not be "new" (default 0)

# Use custom detector
detector = CustomAnomalyDetector(historical_transactions=historical)
```

### Add Custom Detection Method

```python
class ExtendedAnomalyDetector(TransactionAnomalyDetector):
    """Add custom detection logic"""

    def detect_anomalies(self, transactions):
        # Run standard detection
        anomalies = super().detect_anomalies(transactions)

        # Add custom method
        self._detect_category_changes(transactions)
        anomalies.extend(self.anomalies)

        return anomalies

    def _detect_category_changes(self, transactions):
        """Custom: Detect unusual spending categories"""
        # Your custom logic here
        pass
```

### Adjust Severity Scoring

```python
# After detection, adjust severity based on business rules
for anomaly in anomalies:
    # Reduce severity for known merchants even if high amount
    if is_trusted_vendor(anomaly['transaction']['merchant']):
        anomaly['severity_score'] *= 0.7

    # Increase severity for international transactions
    if 'international' in anomaly['transaction']['merchant'].lower():
        anomaly['severity_score'] += 0.2

    # Cap at 1.0
    anomaly['severity_score'] = min(anomaly['severity_score'], 1.0)
```

---

## Troubleshooting

### Problem: No anomalies detected

```python
# Likely causes:
# 1. Not enough historical data
if len(historical_transactions) < 10:
    print("WARNING: Less than 10 historical transactions")
    print("Results may have high false negative rate")

# 2. Current transactions too similar to baseline
# - Can be good (no fraud) or bad (detector misconfigured)

# 3. Threshold too high
# - Reduce z_score_threshold from 2.5 to 2.0
# - Lower severity thresholds for reporting

# Solution: Check baseline statistics
print(f"Mean: ${detector.amount_history}")
print(f"Min: ${min(detector.amount_history)}")
print(f"Max: ${max(detector.amount_history)}")
```

### Problem: Too many false positives

```python
# Solutions:
# 1. Increase z_score threshold
detector.z_score_threshold = 3.0  # More lenient

# 2. Only report critical severity
critical = [a for a in anomalies if a['severity_score'] >= 0.8]

# 3. Recalibrate baseline
# - Run 3-month recalibration
# - Exclude one-time events (vacations, emergencies)

# 4. Check merchant normalization
print(detector._normalize_merchant("Shell/Gas-Station"))
# Should match "Shell Gas Station" purchases
```

### Problem: Missing legitimate transactions

```python
# Ensure proper data format:
required_fields = ['date', 'merchant', 'amount', 'type']

for tx in current:
    for field in required_fields:
        if field not in tx or tx[field] is None:
            print(f"WARNING: Missing {field} in {tx}")
            # Skip or handle default value

# Check date format compatibility
supported_formats = [
    '%Y-%m-%d',
    '%Y-%m-%d %H:%M:%S',
    '%m/%d/%Y',
    '%m/%d/%Y %H:%M:%S'
]

# Verify your dates match one of these
test_date = '2026-03-12 14:30:00'
for fmt in supported_formats:
    try:
        datetime.strptime(test_date, fmt)
        print(f"✓ Format matches: {fmt}")
    except:
        pass
```

---

## Performance Tips

### For Large Datasets (1000+ transactions)

```python
# 1. Process in batches
detector = TransactionAnomalyDetector(historical_transactions=historical)

batch_size = 500
for i in range(0, len(current), batch_size):
    batch = current[i:i+batch_size]
    batch_anomalies = detector.detect_anomalies(batch)
    # Process batch results

# 2. Cache normalized merchants
merchant_cache = {}

def get_normalized_merchant(merchant):
    if merchant not in merchant_cache:
        merchant_cache[merchant] = detector._normalize_merchant(merchant)
    return merchant_cache[merchant]

# 3. Pre-compute baseline statistics
detector._build_baseline()
# Baseline is now cached for multiple runs
```

### Memory Optimization

```python
# Don't keep entire report in memory
def stream_anomalies(transactions):
    """Process and report anomalies one at a time"""
    detector = TransactionAnomalyDetector(historical)
    anomalies = detector.detect_anomalies(transactions)

    for anomaly in anomalies:
        # Process/store one anomaly
        save_to_database(anomaly)
        # Anomaly can then be garbage collected
```

---

## Best Practices

1. **Update baseline quarterly** - Spending patterns evolve
2. **Manual verification** - Always verify critical flags
3. **Keep history** - Store 6+ months for comparison
4. **Monitor trends** - Track false positive rates
5. **Test thoroughly** - Validate against known fraud cases
6. **Document decisions** - Record why certain alerts were ignored
7. **Escalate appropriately** - Clear criteria for contacting bank
8. **Privacy first** - Never share raw transaction data

---

## Support & Debugging

### Enable Debug Output

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('anomaly_detection')

# Add to TransactionAnomalyDetector
class DebugDetector(TransactionAnomalyDetector):
    def detect_anomalies(self, transactions):
        logger.debug(f"Analyzing {len(transactions)} transactions")
        logger.debug(f"Baseline: mean={self.amount_history}, stdev={...}")

        anomalies = super().detect_anomalies(transactions)

        logger.debug(f"Found {len(anomalies)} anomalies")
        return anomalies
```

### Export for Analysis

```python
# Export baseline for inspection
import json

baseline_stats = {
    'transaction_count': len(detector.baseline_transactions),
    'merchants': list(detector.merchant_history.keys()),
    'amount_stats': {
        'min': min(detector.amount_history),
        'max': max(detector.amount_history),
        'mean': sum(detector.amount_history) / len(detector.amount_history),
    }
}

with open('baseline_analysis.json', 'w') as f:
    json.dump(baseline_stats, f, indent=2)
```

---

## Conclusion

This guide provides everything needed to implement effective fraud detection for personal banking. Start with the quick start, then customize based on your specific needs and risk tolerance.
