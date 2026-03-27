'use strict';

/**
 * Error Handling Middleware
 * Centralized error handler for the Express application.
 * Converts errors into consistent JSON responses.
 */

/**
 * 404 Not Found handler.
 * Should be registered after all routes.
 *
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
function notFoundHandler(req, res, next) {
  res.status(404).json({
    success: false,
    error: `Route not found: ${req.method} ${req.originalUrl}`
  });
}

/**
 * Global error handler.
 * Should be registered last, after all routes and other middleware.
 * Express identifies this as an error handler because it has 4 parameters.
 *
 * @param {Error} err
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
function globalErrorHandler(err, req, res, next) {
  // Log the full error for server-side debugging
  console.error('[errorHandler]', {
    message: err.message,
    stack: process.env.NODE_ENV !== 'production' ? err.stack : undefined,
    url: req.originalUrl,
    method: req.method
  });

  // Determine HTTP status code
  let statusCode = err.statusCode || err.status || 500;

  // Handle specific error types
  if (err.name === 'ValidationError') {
    // Mongoose validation error
    statusCode = 400;
    const errors = Object.values(err.errors || {}).map((e) => e.message);
    return res.status(statusCode).json({
      success: false,
      error: 'Validation failed',
      details: errors
    });
  }

  if (err.name === 'CastError') {
    // Mongoose invalid ObjectId
    statusCode = 400;
    return res.status(statusCode).json({
      success: false,
      error: `Invalid value for field: ${err.path}`
    });
  }

  if (err.code === 11000) {
    // MongoDB duplicate key error
    statusCode = 409;
    const field = Object.keys(err.keyValue || {})[0] || 'field';
    return res.status(statusCode).json({
      success: false,
      error: `Duplicate value for ${field}`
    });
  }

  if (err.name === 'SyntaxError' && err.type === 'entity.parse.failed') {
    // Malformed JSON body
    statusCode = 400;
    return res.status(statusCode).json({
      success: false,
      error: 'Invalid JSON in request body'
    });
  }

  // Generic error response
  // In production, don't expose internal error details
  const message =
    process.env.NODE_ENV === 'production' && statusCode === 500
      ? 'An internal server error occurred. Please try again later.'
      : err.message || 'An unexpected error occurred';

  res.status(statusCode).json({
    success: false,
    error: message,
    // Include stack trace only in development
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
}

module.exports = { notFoundHandler, globalErrorHandler };
