## Objective

The objective of this round is to set up the initial backend structure for the Claude Co-Work Financial Assistant project. This includes creating the project repository, setting up the environment configuration, and defining the basic API contract. We will also implement basic authentication and session management to secure the demo environment.

## Implementation Details

1. **Project Setup**: Initialize a new Node.js project with Express.js. Set up the basic file structure as outlined in the project blueprint.

2. **Environment Configuration**: Create an `.env.example` file to manage environment variables. This file will include placeholders for variables such as database connection strings and authentication secrets.

3. **Basic Authentication**: Implement basic authentication using Express middleware. This will involve creating a middleware function that checks for a valid session or token before allowing access to protected routes.

4. **API Contract Definition**: Define the initial set of API endpoints, including routes for authentication and session management. Document the expected request and response formats.

## Files to Create

1. **Project Initialization**:
   - Create a new directory named `claude-financial-assistant`.
   - Inside this directory, run `npm init -y` to initialize a new Node.js project.
   - Install necessary packages: `express`, `dotenv`, `express-session`, `bcrypt`.

2. **Environment Configuration**:
   - Create a file at `/claude-financial-assistant/config/env.example` with the following content:
     ```plaintext
     PORT=3000
     SESSION_SECRET=your-session-secret
     DB_PATH=./database.sqlite
     ```

3. **Basic Authentication**:
   - Create a file at `/claude-financial-assistant/server/middleware/authMiddleware.js` with the following content:
     ```javascript
     const session = require('express-session');

     module.exports = (req, res, next) => {
       if (req.session && req.session.user) {
         return next();
       } else {
         return res.status(401).json({ message: 'Unauthorized' });
       }
     };
     ```

4. **API Contract Definition**:
   - Create a file at `/claude-financial-assistant/server/routes/authRoutes.js` with the following content:
     ```javascript
     const express = require('express');
     const bcrypt = require('bcrypt');
     const router = express.Router();

     // Mock user data
     const users = [{ username: 'demo', password: '$2b$10$...' }]; // Password should be hashed

     router.post('/login', async (req, res) => {
       const { username, password } = req.body;
       const user = users.find(u => u.username === username);
       if (user && await bcrypt.compare(password, user.password)) {
         req.session.user = user;
         res.json({ message: 'Login successful' });
       } else {
         res.status(401).json({ message: 'Invalid credentials' });
       }
     });

     router.post('/logout', (req, res) => {
       req.session.destroy(err => {
         if (err) {
           return res.status(500).json({ message: 'Logout failed' });
         }
         res.json({ message: 'Logout successful' });
       });
     });

     module.exports = router;
     ```

5. **App Setup**:
   - Create a file at `/claude-financial-assistant/server/app.js` with the following content:
     ```javascript
     const express = require('express');
     const session = require('express-session');
     const authRoutes = require('./routes/authRoutes');
     const authMiddleware = require('./middleware/authMiddleware');
     require('dotenv').config();

     const app = express();

     app.use(express.json());
     app.use(session({
       secret: process.env.SESSION_SECRET,
       resave: false,
       saveUninitialized: true,
     }));

     app.use('/auth', authRoutes);

     app.get('/protected', authMiddleware, (req, res) => {
       res.json({ message: 'This is a protected route' });
     });

     const PORT = process.env.PORT || 3000;
     app.listen(PORT, () => {
       console.log(`Server running on port ${PORT}`);
     });
     ```

## Verification Criteria

- Ensure the project directory and file structure are correctly set up as specified.
- Verify that the server starts without errors and listens on the specified port.
- Test the `/auth/login` endpoint with valid and invalid credentials to ensure it responds correctly.
- Verify that the `/auth/logout` endpoint destroys the session and responds with a success message.
- Confirm that the `/protected` route is inaccessible without a valid session and accessible with one.
- Check that environment variables are loaded correctly from the `.env.example` file.