# Claude Rules
# These rules are static. They apply to all code generation for this connection.

## Code Standards
- Write clean, well-documented code
- Follow existing project conventions
- Include inline comments for complex logic
- Handle errors gracefully
- Use proper TypeScript types throughout

## Output Rules
- Place all generated code in the result package using the required JSON schema
- Use the file paths specified in the instructions
- Only create or modify files explicitly listed in the instructions
- Do not touch files from previous rounds unless instructed

## Quality
- Write testable code (pure functions, dependency injection where appropriate)
- Consider edge cases and input validation
- Follow the testing patterns described in the blueprint
