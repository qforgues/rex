## Objective

The objective for this round is to integrate the FreshBooks API to fetch invoice data and ensure that the UI can communicate with the backend via the defined API endpoints. This will involve creating a service to interact with the FreshBooks API and updating the necessary controller and route to handle the data fetching and display.

## Implementation Details

1. **FreshBooks API Integration**:
   - Create a service in the `/server/services` directory to handle communication with the FreshBooks API.
   - The service should authenticate with FreshBooks and fetch invoice data.

2. **Controller Update**:
   - Update the `financeController.js` to include a function that utilizes the FreshBooks service to fetch and return invoice data.

3. **Route Update**:
   - Update the `financeRoutes.js` to add a new endpoint for fetching invoice data.

4. **Environment Variables**:
   - Ensure that necessary API credentials are stored in the `.env` file and accessed securely.

## Files to Create

### `/server/services/freshBooksApi.js`

```javascript
const axios = require('axios');

class FreshBooksApi {
  constructor() {
    this.baseUrl = process.env.FRESHBOOKS_API_URL;
    this.token = process.env.FRESHBOOKS_API_TOKEN;
  }

  async fetchInvoices() {
    try {
      const response = await axios.get(`${this.baseUrl}/invoices`, {
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      });
      return response.data;
    } catch (error) {
      console.error('Error fetching invoices from FreshBooks:', error);
      throw new Error('Failed to fetch invoices');
    }
  }
}

module.exports = new FreshBooksApi();
```

## Files to Modify

### `/server/controllers/financeController.js`

Add the following function to handle fetching invoice data:

```javascript
const freshBooksApi = require('../services/freshBooksApi');

exports.getInvoices = async (req, res) => {
  try {
    const invoices = await freshBooksApi.fetchInvoices();
    res.status(200).json(invoices);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch invoices' });
  }
};
```

### `/server/routes/financeRoutes.js`

Add a new route for fetching invoices:

```javascript
const express = require('express');
const router = express.Router();
const financeController = require('../controllers/financeController');

router.get('/invoices', financeController.getInvoices);

module.exports = router;
```

### `/config/env.example`

Add placeholders for FreshBooks API credentials:

```
FRESHBOOKS_API_URL=https://api.freshbooks.com
FRESHBOOKS_API_TOKEN=your_freshbooks_api_token_here
```

## Verification Criteria

- **Service Functionality**: The `freshBooksApi.js` service should correctly authenticate and fetch invoice data from FreshBooks.
- **Controller Response**: The `getInvoices` function in `financeController.js` should return invoice data in JSON format.
- **Route Accessibility**: The `/invoices` endpoint in `financeRoutes.js` should be accessible and return the correct data when called.
- **Environment Configuration**: Ensure that the `.env` file contains valid FreshBooks API credentials and that they are correctly loaded by the application.
- **Error Handling**: Verify that any errors during the API call are logged and an appropriate error message is returned to the client.
- **Manual Testing**: Use a tool like Postman to manually test the `/invoices` endpoint and confirm it returns the expected data.