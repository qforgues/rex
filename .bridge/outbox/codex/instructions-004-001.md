## Objective

The objective of this round is to implement the FreshBooks integration to fetch and display invoice data. This involves creating a service to interact with the FreshBooks API, defining the necessary API endpoints, and ensuring that the data is correctly retrieved and displayed in the application.

## Implementation Details

1. **FreshBooks API Integration**: Implement a service to handle communication with the FreshBooks API. This service will be responsible for authenticating requests and fetching invoice data.

2. **API Endpoint**: Define an API endpoint that the UI can call to request invoice data. This endpoint will use the FreshBooks service to retrieve data and return it in a suitable format.

3. **Data Handling**: Ensure that the retrieved invoice data is processed and formatted correctly for display in the application.

4. **Error Handling**: Implement error handling to manage any issues that arise during API requests, such as network errors or authentication failures.

## Files to Create

1. **/server/services/freshBooksApi.js**

   - **Function**: `fetchInvoices()`
     - **Description**: Fetches invoice data from the FreshBooks API.
     - **Signature**: `async function fetchInvoices(): Promise<any>`
     - **Behavior**: Makes an authenticated request to the FreshBooks API to retrieve invoice data. Returns the data in JSON format.
     - **Edge Cases**: Handle network errors, authentication errors, and unexpected API responses.

2. **/server/controllers/financeController.js**

   - **Function**: `getInvoices(req, res)`
     - **Description**: Controller function to handle requests for invoice data.
     - **Signature**: `async function getInvoices(req: Request, res: Response): Promise<void>`
     - **Behavior**: Calls `fetchInvoices()` from the FreshBooks service and sends the data in the response. Handles errors by sending an appropriate HTTP status and message.
     - **Edge Cases**: Ensure proper error messages and status codes are returned in case of failures.

3. **/server/routes/financeRoutes.js**

   - **Route**: Define a new route for fetching invoices.
     - **Path**: `/api/invoices`
     - **Method**: `GET`
     - **Handler**: `financeController.getInvoices`

## Verification Criteria

1. **Functionality**: The `/api/invoices` endpoint should successfully return invoice data from FreshBooks when accessed.

2. **Error Handling**: The system should handle errors gracefully, returning appropriate HTTP status codes and error messages when API requests fail.

3. **Data Format**: The invoice data returned by the endpoint should be in a JSON format that the UI can process and display.

4. **Testing**: Write unit tests for the `fetchInvoices()` function to ensure it correctly handles API requests and errors. Use mock data to simulate API responses.

5. **Manual Testing**: Manually test the endpoint using a tool like Postman to verify that it returns the expected data and handles errors appropriately.