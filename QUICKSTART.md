# Statement Organizer - Quick Start Guide

Everything is ready to test! Here's how to get started in 5 minutes.

## ✅ What You Have

- ✓ **Skill** - Complete statement-organizer skill with documentation
- ✓ **Sample Data** - 3 test statements (Banco Popular, Dart Bank, Chase Credit Card)
- ✓ **Dashboard UI** - Interactive interface to manage statements
- ✓ **CLI Tool** - Command-line interface for processing
- ✓ **Folder Structure** - Pre-organized folders for all account types
- ✓ **Documentation** - Comprehensive guides and examples

## 🚀 Start Here

### Option 1: Visual Dashboard (Easiest)

1. **Open the dashboard in your browser:**
   ```
   /sessions/amazing-sharp-clarke/mnt/rex/statement-dashboard.html
   ```

2. **Click "Process All" button** to run the skill on sample statements

3. **Check the "Logs" folder** for processing results

### Option 2: Command Line

```bash
# Process all sample statements
python /sessions/amazing-sharp-clarke/mnt/rex/statement-organizer/scripts/cli.py process-all /sessions/amazing-sharp-clarke/mnt/rex/Statements/

# Or process a single statement
python /sessions/amazing-sharp-clarke/mnt/rex/statement-organizer/scripts/cli.py process "/sessions/amazing-sharp-clarke/mnt/rex/Statements/Personal/Joint/Banks/Banco-Popular-Joint-2026-03.csv"

# Check status
python /sessions/amazing-sharp-clarke/mnt/rex/statement-organizer/scripts/cli.py status --directory "/sessions/amazing-sharp-clarke/mnt/rex/Statements/"
```

### Option 3: Ask Claude

Simply ask:
```
Process all my statement samples and show me the logs
```

Claude will run the skill and show you the results.

## 📂 Folder Locations

Everything lives in: `/sessions/amazing-sharp-clarke/mnt/rex/`

```
rex/
├── Statements/                    # Your statement files and logs
│   ├── Personal/Joint/Banks/      # Joint accounts
│   ├── Personal/You/Banks/        # Your personal accounts
│   ├── Personal/You/Credit_Cards/
│   ├── Business-You/Banks/        # Portal42 (Dart Bank here)
│   ├── Logs/                      # Processing results
│   └── README.md                  # Full documentation
│
├── statement-organizer/           # The skill
│   ├── SKILL.md                   # Complete skill documentation
│   ├── scripts/
│   │   ├── process_statement.py   # Core processing logic
│   │   └── cli.py                 # Command-line tool
│   └── evals/                     # Test case documentation
│
├── statement-organizer-workspace/ # Test results
│   └── iteration-1/
│       ├── eval-viewer.html       # Interactive evaluation report
│       └── benchmark.json         # Performance metrics
│
└── statement-dashboard.html       # Dashboard UI
```

## 📊 Sample Files

Three statements are ready to test:

| File | Type | Transactions | Test |
|------|------|--------------|------|
| `Banco-Popular-Joint-2026-03.csv` | Bank | 15 | Spanish format detection |
| `Dart-Bank-2026-03.csv` | Bank | 14 | FreshBooks matching |
| `Chase-Personal-2026-03.csv` | Credit Card | 15 | Anomaly detection |

Location: `/Statements/{appropriate folder}/`

## 🎯 Test Scenarios

After processing samples, you'll see:

### 1. Format Learning
- ✓ Spanish column detection (Banco Popular)
- ✓ Format mappings stored in `.statement-formats.json`
- ✓ All transactions parsed (15/15, 14/14, 15/15)

### 2. FreshBooks Integration
- ✓ Dart Bank transactions matched to dispensary invoices
- ✓ 3-category report: Matched / Ambiguous / Unmatched
- ✓ CSV report in Logs folder

### 3. Anomaly Detection
- ✓ Unusual purchase detection on Chase card
- ✓ Flagged items with severity levels
- ✓ Suspicious merchant identification

## 📈 What Happens Next

After you click "Process All":

1. **Detection** - Skill identifies each statement type
2. **Learning** - First time: learns column mappings; second time: uses cached mappings
3. **Parsing** - Extracts transactions with date, amount, merchant
4. **Matching** - (Dart Bank only) Matches to FreshBooks invoices
5. **Logging** - Creates detailed logs in `/Statements/Logs/`
6. **Reporting** - Generates CSV reports with results

## 📋 Check Results

After processing, view:

```
/Statements/Logs/
├── statement-processing-2026-03-23.log    # What was processed
├── freshbooks-sync-2026-03-23.log         # Invoice matching details
└── freshbooks-matches-2026-03-23.csv      # 3-category match report
```

## 🔧 Configuration (Optional)

### FreshBooks API

To enable actual invoice marking (not just reporting):

1. Create file: `/Statements/.freshbooks-config.json`
2. Add your credentials:
   ```json
   {
     "api_token": "your_api_token_here",
     "account_id": "your_account_id"
   }
   ```

### Anomaly Detection Thresholds

Defaults are conservative. After reviewing flagged items, let Claude adjust thresholds to match your patterns.

## ✨ Next Steps

### Immediate (Today)
1. ✓ Process sample statements
2. ✓ Review logs and reports
3. ✓ Verify format detection worked
4. ✓ Check FreshBooks matching logic

### Short-term (This Week)
1. Add your real bank statements
2. Test with actual Banco Popular exports
3. Review anomaly detection for your patterns
4. Set up FreshBooks credentials

### Medium-term (This Month)
1. Automate on the 1st of each month (Portal42 payroll date)
2. Build trend analysis
3. Calibrate anomaly thresholds
4. Integrate with your accounting workflow

## 🆘 Troubleshooting

**Not seeing results?**
- Check `/Statements/Logs/` for error messages
- Make sure sample files exist in expected folders
- Try running CLI directly for more verbose output

**Format not detected?**
- Open the CSV and confirm column headers are visible
- Manually specify bank with `--bank` parameter
- Format will be learned on first pass

**FreshBooks not connecting?**
- Check credentials in `.freshbooks-config.json`
- Verify API token hasn't expired
- Check logs for specific error message

## 💡 Pro Tips

1. **Name statements clearly** - Use consistent naming (e.g., `Banco-Popular-Joint-2026-03.csv`)
2. **Learn once, reuse forever** - After first processing, future statements auto-parse
3. **Review logs first** - All issues are logged with helpful context
4. **Start with samples** - Understand the flow before adding real data
5. **Backup your statements** - Keep originals safe before processing

## 📖 Full Documentation

For comprehensive details, see:
- `/Statements/README.md` - Complete setup guide
- `/statement-organizer/SKILL.md` - Full skill documentation
- `/statement-organizer-workspace/iteration-1/eval-viewer.html` - Test results

## 🎉 Ready?

**Pick one and go:**
1. Open dashboard → Click "Process All"
2. Run CLI command (see Option 2 above)
3. Ask Claude to "process my sample statements"

That's it! Let's see those statements get organized! 🚀
