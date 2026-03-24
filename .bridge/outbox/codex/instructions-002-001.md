## Objective

The objective of this round is to implement the basic authentication and session management for the Claude Co-Work Financial Assistant backend. This will involve creating the necessary middleware and configuration files to handle user authentication and session management for demo purposes.

## Implementation Details

1. **Authentication Middleware**: Implement middleware to handle user authentication using basic authentication. This will involve verifying user credentials against a predefined set of demo users.

2. **Session Management**: Implement session management to maintain user sessions across requests. This will involve setting up session storage using SQLite.

3. **Configuration**: Create a configuration file to manage authentication-related settings, such as session secret and demo user credentials.

4. **Routes**: Define routes for login and logout actions to manage user sessions.

5. **Security**: Ensure that user passwords are hashed and stored securely.

## Files to Create

1. **`/server/middleware/authMiddleware.js`**
   - **Function**: `authenticateUser(req, res, next)`
     - **Description**: Middleware function to authenticate users using basic authentication. It should check the `Authorization` header for credentials, verify them against demo users, and proceed if valid.
     - **Parameters**: `req` (Express Request), `res` (Express Response), `next` (Express NextFunction)
     - **Behavior**: If authentication is successful, attach user information to the request object and call `next()`. If not, respond with a 401 status code.

2. **`/server/middleware/sessionMiddleware.js`**
   - **Function**: `initializeSession(app)`
     - **Description**: Function to set up session management using `express-session` and SQLite as the session store.
     - **Parameters**: `app` (Express Application)
     - **Behavior**: Configure the session middleware with a secret, store, and other session options.

3. **`/config/authConfig.js`**
   - **Content**: Export an object containing authentication-related configurations such as session secret, demo user credentials, and password hashing settings.

4. **`/server/routes/authRoutes.js`**
   - **Routes**:
     - `POST /login`: Route to handle user login. It should authenticate the user and establish a session.
     - `POST /logout`: Route to handle user logout. It should destroy the user session.

5. **`/server/models/User.js`**
   - **Description**: Define a `User` model to represent demo users with fields for username and hashed password.

## Verification Criteria

- **Authentication Middleware**: Verify that the `authenticateUser` middleware correctly checks user credentials and allows access to protected routes only for authenticated users.

- **Session Management**: Ensure that sessions are created upon successful login and destroyed upon logout. Verify that session data is stored in SQLite.

- **Configuration**: Check that authentication settings are correctly loaded from `authConfig.js` and used throughout the authentication process.

- **Routes**: Test the `/login` and `/logout` routes to ensure they handle user sessions correctly. Verify that a user can log in with valid credentials and that their session persists across requests.

- **Security**: Confirm that user passwords are hashed before storage and that only hashed passwords are stored in the database.

- **Testing**: Implement basic tests to verify the functionality of the authentication middleware and routes. Ensure that all tests pass successfully.