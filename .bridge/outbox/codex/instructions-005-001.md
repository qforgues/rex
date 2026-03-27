## Objective

The objective of this round is to implement the CSV file upload and parsing functionality. This involves creating an endpoint that allows users to upload CSV files, parsing the contents of these files, and storing the parsed data in the SQLite database. This functionality is crucial for processing bank and credit card statements, which will later be used to generate financial insights.

## Implementation Details

1. **CSV File Upload Endpoint**: Create a new API endpoint to handle CSV file uploads. This endpoint should accept a CSV file, parse its contents, and store the parsed data in the SQLite database.

2. **CSV Parsing Service**: Implement a service that uses a CSV parsing library to read and parse the contents of the uploaded CSV file. This service should handle edge cases such as empty files, malformed CSV data, and files with unexpected columns.

3. **Database Model**: Ensure that the `Transaction` model in the `/models/Transaction.js` file is set up to store the parsed data. The model should include fields such as `date`, `description`, `amount`, and `category`.

4. **Error Handling**: Implement error handling to manage scenarios where the CSV file is invalid or the database operation fails. Return appropriate HTTP status codes and error messages.

## Files to Create

### 1. `/server/routes/financeRoutes.js`

Add a new route for handling CSV file uploads.

```javascript
const express = require('express');
const financeController = require('../controllers/financeController');
const router = express.Router();

router.post('/upload-csv', financeController.uploadCsv);

module.exports = router;
```

### 2. `/server/controllers/financeController.js`

Implement the `uploadCsv` function to handle the CSV upload logic.

```javascript
const csvParser = require('../services/csvParser');
const Transaction = require('../models/Transaction');

exports.uploadCsv = async (req, res) => {
  try {
    const transactions = await csvParser.parseCsv(req.file);
    await Transaction.bulkCreate(transactions);
    res.status(200).json({ message: 'CSV file processed successfully', transactions });
  } catch (error) {
    res.status(400).json({ error: error.message });
  }
};
```

### 3. `/server/services/csvParser.js`

Create a service to parse the CSV file.

```javascript
const csv = require('csv-parser');
const fs = require('fs');

exports.parseCsv = (file) => {
  return new Promise((resolve, reject) => {
    const transactions = [];
    fs.createReadStream(file.path)
      .pipe(csv())
      .on('data', (row) => {
        transactions.push({
          date: row['Date'],
          description: row['Description'],
          amount: parseFloat(row['Amount']),
          category: row['Category'],
        });
      })
      .on('end', () => {
        resolve(transactions);
      })
      .on('error', (error) => {
        reject(error);
      });
  });
};
```

## Verification Criteria

1. **Endpoint Functionality**: Verify that the `/upload-csv` endpoint accepts a CSV file and returns a 200 status code with a success message and the parsed transactions.

2. **CSV Parsing**: Test the CSV parsing service with various CSV files, including edge cases such as empty files, files with missing columns, and malformed data. Ensure that it correctly parses and returns the expected transaction objects.

3. **Database Storage**: Confirm that the parsed transactions are correctly stored in the SQLite database by querying the `Transaction` table after a successful upload.

4. **Error Handling**: Test error scenarios, such as uploading a non-CSV file or a CSV file with invalid data, and ensure that the system returns appropriate error messages and status codes.

5. **Integration Test**: Write an integration test to simulate the entire upload process, from file upload to database storage, ensuring that all components work together seamlessly.