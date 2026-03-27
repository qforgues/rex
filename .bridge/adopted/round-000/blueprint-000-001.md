# Revised Project Blueprint: Claude Co-Work Financial Assistant

## Overview

This project aims to create a functional backend for an existing UI in the Claude Co-Work Financial Assistant. The primary goal is to ensure that all UI buttons and actions perform as expected, enabling the generation of demo documents to validate the flow process. This involves integrating with FreshBooks for invoice management, processing CSV files from banks and credit cards, and generating financial insights. The project will focus on delivering a demo-ready system that can produce accurate financial reports and documents.

## Technical Architecture

- **Backend**: Node.js with Express.js for handling API requests and data processing.
- **Database**: SQLite for lightweight data storage during the demo phase, with JSON flat files for seed data.
- **PDF Generation**: PDFKit for generating demo documents from HTML templates.
- **Security**: Basic authentication with session management for demo purposes.
- **UI Integration**: Ensure seamless communication between the existing UI and the new backend via RESTful API endpoints.
- **Environment Configuration**: Use `.env` files for managing environment variables.

## MVP Scope

1. **UI Action Inventory**: Document all UI buttons and expected actions.
2. **API Contract Definition**: Define API endpoints, request/response formats, and HTTP methods.
3. **Demo Document Generation**: Create demo documents using PDFKit, with predefined templates and seed data.
4. **FreshBooks Integration**: Basic integration to fetch and display invoice data.
5. **CSV File Processing**: Ability to upload and parse CSV files, storing results in SQLite.
6. **Financial Overview Dashboard**: Display financial summaries using seed data.
7. **Authentication**: Implement basic authentication for demo purposes.

## Implementation Phases

### Phase 0: UI Audit and Documentation
- Conduct a thorough audit of the existing UI.
- Document all buttons, actions, and expected outputs.
- Define the flow process and data requirements for demo documents.

### Phase 1: Backend Setup and API Contract
- Set up the project repository and environment.
- Define API endpoints, methods, and data formats.
- Implement basic authentication and session management.

### Phase 2: Demo Document Generation and Data Handling
- Develop templates for demo documents using Handlebars.
- Implement PDF generation using PDFKit.
- Create seed data files in JSON format and set up SQLite for data storage.
- Implement CSV file upload and parsing functionality.

### Phase 3: UI Integration and FreshBooks API
- Ensure the UI can communicate with the backend via defined API endpoints.
- Integrate with FreshBooks API to fetch invoice data.
- Display financial summaries on the dashboard using seed data.

### Phase 4: Testing, Validation, and Optimization
- Conduct unit, integration, and manual testing to ensure functionality.
- Validate demo documents with stakeholders.
- Optimize performance and fix any bugs.

## File Structure

```
/claude-financial-assistant
  /server
    /controllers
      authController.js
      documentController.js
      financeController.js
    /models
      User.js
      Invoice.js
      Transaction.js
    /routes
      authRoutes.js
      documentRoutes.js
      financeRoutes.js
    /services
      csvParser.js
      freshBooksApi.js
      pdfGenerator.js
    /middleware
      authMiddleware.js
      errorHandlingMiddleware.js
    app.js
  /config
    db.js
    authConfig.js
    env.example
  /templates
    demoTemplate.hbs
  /seeds
    demoData.json
  /tests
    /server
      authController.test.js
      documentController.test.js
      financeController.test.js
      csvParser.test.js
      freshBooksApi.test.js
      pdfGenerator.test.js
  package.json
  README.md
```

## Testing Strategy

- **Unit Testing**: Use Jest for testing backend logic and services.
- **Integration Testing**: Test API endpoints and data handling using Supertest.
- **Manual Testing**: Conduct manual testing sessions to ensure UI actions trigger expected backend processes.
- **Validation Testing**: Stakeholders review demo documents to ensure accuracy and completeness.

## Completion Criteria

- All UI actions are documented and connected to backend processes.
- API endpoints are defined and functional, with correct request/response handling.
- Demo documents are generated accurately and validated by stakeholders.
- FreshBooks integration displays invoice data correctly.
- CSV files can be uploaded, parsed, and stored in SQLite.
- Financial dashboard displays summaries using seed data.
- Basic authentication is implemented, and the system is secure for demo purposes.
- All tests pass successfully, and the system is free of critical bugs.
- The application is ready for demo, with all flow scenarios validated by stakeholders.