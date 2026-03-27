# Statement Organizer Skill

Financial statement automation for organizing bank and credit card statements, learning formats once, and syncing with FreshBooks.

## Quick Start

1. Read `SKILL.md` for full documentation
2. Set up FreshBooks API token (environment variable or `.freshbooks-config.json`)
3. Drop CSV statements into your `Statements/` folder structure
4. The skill handles format learning, organization, and FreshBooks syncing

## Key Files

- **SKILL.md** - Full documentation, triggers, usage examples, troubleshooting
- **scripts/process_statement.py** - Core processing engine (format detection, parsing, matching, logging)

## Folder Structure

```
statement-organizer/
├── SKILL.md                      # Skill documentation
├── README.md                     # This file
└── scripts/
    └── process_statement.py      # Main processing script
```

## Features

✓ **Format Detection & Learning** - Learn statement formats once, reuse forever
✓ **Statement Organization** - Auto-organize into Personal/Joint/You/Courtney/Business folders
✓ **FreshBooks Integration** - Match transactions by amount + dispensary name, mark invoices paid
✓ **Logging & Reporting** - Detailed logs and CSV reports of all matches, ambiguities, mismatches

## Testing

Test cases are defined in `evals/evals.json`. Run tests to verify the skill works correctly.
