# Anomaly Detection Logic - Detailed Explanation

## Overview

This document explains the technical implementation and mathematical reasoning behind each anomaly detection method.

---

## 1. Statistical Outlier Detection (Z-Score Method)

### What It Does
Identifies transactions with amounts significantly outside the normal spending range.

### Mathematical Formula

```
Z-score = |Amount - Mean| / Standard Deviation

Flag if Z-score > 2.5
```

### Example Calculation

**Historical spending:**
- Feb transactions: $85, $52, $34, $6, $15, $28, $18, $92, $49, $45, $51, $5, $29, $88, $17
- Mean = $802 / 15 = $53.45
- Standard Deviation ≈ $27.84

**March transaction: $5,000 (Crypto platform)**

```
Z-score = |5000 - 53.45| / 27.84
        = 4946.55 / 27.84
        = 177.6

Threshold: 177.6 > 2.5 → FLAG AS ANOMALY
Severity: min(177.6 / 5.0, 1.0) = 1.0 (CRITICAL)
```

### Why 2.5 Standard Deviations?
- In a normal distribution, 2.5σ includes ~98.8% of data
- Only 0.2% of legitimate transactions fall here
- Balances sensitivity with false positive rate
- Industry standard for fraud detection

### Advantages
- Simple, well-understood statistical method
- Works regardless of merchant type
- Naturally adapts to changing baselines
- Robust mathematical foundation

### Limitations
- Assumes roughly normal distribution
- May miss fraud with "average-sized" amounts
- Needs at least 3-5 data points to be reliable

---

## 2. Merchant Pattern Analysis

### What It Does
Tracks transaction patterns by merchant to identify:
- New merchants (first time ever)
- Rare merchants (very infrequent usage)

### Implementation

```python
# Build merchant frequency from historical data
merchant_frequency = {
    'Whole Foods': 4,
    'Amazon': 2,
    'Target': 1,
    'Shell Gas': 2,
    'Starbucks': 2
}

# Classify current transaction merchants
For each current transaction:
    merchant = normalize(transaction['merchant'])
    frequency = merchant_frequency.get(merchant, 0)

    if frequency == 0:
        Flag as NEW_MERCHANT (severity 0.6)
    elif frequency < 2:
        Flag as RARE_MERCHANT (severity 0.4)
```

### Example

**Transaction: Crypto Exchange Platform - $5,000**
- Normalized: "cryptoexchangeplatform"
- Frequency count: 0
- Never seen before → FLAG

**Why this works:**
- Fraud typically uses unfamiliar merchants
- Users have consistent spending patterns
- New vendors warrant investigation even if amount is normal

### Advantages
- Very effective at catching new fraud vectors
- Identifies unusual vendor relationships
- Complements amount-based detection

### Limitations
- Requires diverse historical data
- False positives if user genuinely uses new vendors
- Merchant name variations complicate matching

---

## 3. Time-Based Anomaly Detection

### What It Does
Identifies transactions at unusual times of day.

### Implementation

```python
# Calculate transaction frequency by hour
time_histogram = {
    9: 3,   # 9 AM - 3 transactions
    10: 2,  # 10 AM
    14: 4,  # 2 PM
    15: 2,  # 3 PM
    ... (other hours have 0-1)
}

average_per_hour = total_transactions / 24

# Flag unusual hours
For each hour:
    frequency = time_histogram[hour]
    if frequency < average_per_hour * 0.2:
        Flag transaction at this hour (severity 0.35)
```

### Example

**Data:**
- 15 historical transactions
- Average per hour: 15 / 24 = 0.625 per hour
- Threshold: 0.625 * 0.2 = 0.125 (essentially no transactions)

**Transaction at 3:22 AM:**
- Hour 3 frequency: 0
- 0 < 0.125 → FLAG

**Most common hours:**
- 9:00 AM (3 times)
- 2:00 PM (4 times)
- 3:00 PM (2 times)

### Why This Works
- Legitimate shopping happens during business hours
- Fraud often happens when victims are asleep
- Behavioral pattern that's hard for fraudsters to fake

### Advantages
- Catches opportunistic fraud
- Low false positive rate
- Simple to understand

### Limitations
- Not effective for online purchases (same hourly patterns)
- Misses fraud during normal hours
- Timezone changes complicate analysis

---

## 4. Duplicate Detection

### What It Does
Identifies identical or near-identical transactions within short time periods.

### Implementation

```python
# Track seen transactions
seen_transactions = {}

For each transaction:
    key = f"{amount}|{merchant_normalized}"

    if key in seen_transactions:
        # Duplicate found
        previous = seen_transactions[key]
        Flag as DUPLICATE (severity 0.8)
        Note: timestamp of previous transaction
    else:
        seen_transactions[key] = transaction
```

### Example

**March statement:**
- 10:10 AM: Target, $42.50, "Shopping"
- 10:10 AM: Target, $42.50, "Shopping"

**Detection:**
- Key: "42.50|target"
- Second transaction matches key
- DUPLICATE FOUND → FLAG (severity 0.8)

### Why This Works
- Legitimate duplicates are extremely rare
- Strong indicator of:
  - Processing errors (merchant charged twice)
  - Fraudulent repeat charges
- Timestamp matching adds confidence

### Advantages
- Very high precision (few false positives)
- High severity warranted
- Easy to resolve (contact merchant/bank)

### Limitations
- Only catches exact/near-exact duplicates
- Misses legitimate double-charges with small variations
- May not detect time-delayed duplicates (different day)

---

## 5. Frequency & Concentration Analysis

### What It Does
Detects unusual concentrations of high-value transactions.

### Implementation

```python
# Calculate spending metrics
total_amount = sum(all_amounts)
transaction_count = len(all_transactions)
average_per_tx = total_amount / transaction_count

# Count high-value transactions
high_value_count = 0
for tx in all_transactions:
    if amount > average_per_tx * 2:
        high_value_count += 1

# Calculate concentration ratio
concentration_ratio = high_value_count / transaction_count

# Flag if excessive concentration
if concentration_ratio > 0.3:
    Flag as FREQUENCY_ANOMALY (severity 0.5)
```

### Example

**March statement:**
- Total amount: ~$11,000
- Transaction count: 16
- Average per transaction: $688

**High-value transactions (>$1,376):**
1. Crypto Exchange: $5,000
2. Hotel Resort: $3,250
3. Midnight Electronics: $1,250
4. Overseas Vendor: $875

- High-value count: 4
- Concentration: 4/16 = 0.25 (25%)
- 25% > 30% threshold? → Not quite, but borderline

### Why This Works
- Legitimate spending is distributed
- Fraud sprees concentrate activity
- Suggests planned, coordinated fraud activity

### Advantages
- Catches broad fraud campaigns
- Identifies spending pattern changes
- Useful for detecting account takeover

### Limitations
- May flag legitimate shopping sprees
- Requires baseline adjustment for events (holidays)
- Threshold is subjective (30% chosen as balance point)

---

## Severity Scoring System

### Formula by Anomaly Type

```
STATISTICAL_OUTLIER:
    severity = min(z_score / 5.0, 1.0)
    Range: 0.5 (mildly unusual) to 1.0 (extremely unusual)

NEW_MERCHANT:
    severity = 0.6 (moderate concern)

RARE_MERCHANT:
    severity = 0.4 (lower concern)

TIME_ANOMALY:
    severity = 0.35 (informational)

DUPLICATE:
    severity = 0.8 (high concern - clear error/fraud)

FREQUENCY_ANOMALY:
    severity = 0.5 (moderate concern)
```

### Interpretation

```
0.0 - 0.3:  INFO     - Log for reference, likely harmless
0.3 - 0.5:  WARNING  - Review, but probably legitimate
0.5 - 0.7:  ALERT    - Investigate, possible fraud
0.7 - 1.0:  CRITICAL - Immediate action required
```

### Why Composite Scoring?
- Multiple detection methods increase confidence
- Severity reflects both likelihood and impact
- Critical threshold (0.7+) is conservative
- Forces review without creating alert fatigue

---

## Detection Combination Strategy

### Single-Method Triggers
Each detection method can independently trigger an anomaly alert.

### Example Flows

**Scenario 1: New merchant, large amount, unusual time**
- Statistical outlier: Z=5.8 → severity 1.0
- New merchant → severity 0.6
- Time anomaly → severity 0.35
- **Result:** Multiple flags increase confidence → CRITICAL

**Scenario 2: Legitimate large purchase**
- Statistical outlier: Z=3.2 → severity 0.64
- Established merchant (Amazon) → no flag
- Normal time (2 PM) → no flag
- **Result:** Only amount is flagged → WARNING (less concerning)

**Scenario 3: Duplicate charge**
- Duplicate detected → severity 0.8
- Amount is normal → no statistical flag
- Known merchant → no merchant flag
- **Result:** Clear error/fraud indicator → HIGH priority

---

## Adaptive Baseline System

### Quarterly Recalibration

```python
def quarterly_recalibration():
    # Use previous 3 months of legitimate transactions
    historical = get_verified_transactions(last_90_days)

    # Recalculate baseline metrics
    new_mean = calculate_mean(historical)
    new_stdev = calculate_stdev(historical)
    new_merchants = extract_merchant_list(historical)
    new_hours = calculate_hourly_distribution(historical)

    # Update detector
    detector.baseline_mean = new_mean
    detector.baseline_stdev = new_stdev
    detector.merchant_frequency = new_merchants
    detector.time_histogram = new_hours
```

### Why Adaptive?
- Spending patterns naturally change over time
- Baselines become stale without updates
- Quarterly updates balance freshness vs. stability
- Manual override for major life changes

---

## Implementation Considerations

### Data Normalization
```python
def normalize_merchant(merchant_string):
    # Remove punctuation, spaces, special characters
    normalized = re.sub(r'[^a-z0-9]', '', merchant_string.lower())
    return normalized

# Examples:
'Shell Gas Station' → 'shellgasstation'
'Shell/Gas-Station' → 'shellgasstation'
'SHELL GAS STATION' → 'shellgasstation'
```

### Missing Data Handling
```python
# Amount field
if amount is None or amount == '':
    skip_transaction()

# Date field
if date is None:
    set_hour = 0  # Default to midnight for statistical fairness

# Merchant field
if merchant is None or merchant == '':
    merchant = 'UNKNOWN_MERCHANT'
```

### Edge Cases
1. First month of data (no baseline)
   - Use standard deviations approach
   - Lower severity scores
   - Require multiple flags for alerts

2. Account takeover (sudden spending spike)
   - Multiple anomalies cluster together
   - Severity compounding recommended
   - Requires immediate action

3. Legitimate spending changes
   - Vacation spike
   - Home purchase
   - Medical emergency
   - **Action:** Manual baseline reset after verification

---

## Performance Characteristics

### Computational Complexity
- O(n) for each detection method
- O(n log n) if results sorting required
- Total: O(n) for 5-method system

### Memory Usage
- Baseline storage: O(m) where m = historical transactions
- Detection: O(n) for current transactions
- Report generation: O(n + k) where k = anomalies found

### Scalability
- Handles 500+ transactions easily
- Baseline of 10,000+ transactions feasible
- Real-time processing possible for single transactions

---

## Validation & Testing

### Precision vs. Recall Tradeoff
```
Precision = Correct Anomalies / All Flagged
Recall = Caught Anomalies / All True Anomalies

Current tuning:
- High precision (few false positives)
- Moderate recall (catches most fraud)
- Threshold adjustable based on risk tolerance
```

### Recommended Testing
1. Test against known fraudulent statements
2. Validate against false positive cases
3. Measure detection latency
4. Monitor accuracy over time

---

## Conclusion

The five-method approach provides comprehensive, interpretable fraud detection:

1. **Statistical outliers** catch high-impact fraud
2. **Merchant patterns** identify new fraud vectors
3. **Time anomalies** catch opportunistic fraud
4. **Duplicates** identify processing errors/fraud
5. **Frequency analysis** catches coordinated fraud

Each method can stand alone, creating defense-in-depth architecture. The severity scoring allows prioritization and reduces alert fatigue.
