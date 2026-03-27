require('dotenv').config({ path: require('path').join(__dirname, '../.env') });
const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

// Serve dashboard HTML
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, '../statement-dashboard.html'));
});

// Chat proxy — keeps API key server-side, avoids CORS
app.post('/api/chat', async (req, res) => {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: 'ANTHROPIC_API_KEY not set in .env' });
  }

  const { messages } = req.body;
  if (!messages) return res.status(400).json({ error: 'messages required' });

  try {
    const upstream = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-sonnet-4-6',
        max_tokens: 1024,
        system: 'You are a helpful assistant for the Statement Organizer tool. Help users process bank/credit card statements, fix Python script errors, set up FreshBooks integration, and manage their financial data folders. Be concise and practical.',
        messages
      })
    });

    const data = await upstream.json();
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// List log files
app.get('/api/logs', (req, res) => {
  const logsDir = path.join(__dirname, '../Statements/Logs');
  if (!fs.existsSync(logsDir)) return res.json({ files: [] });

  const files = fs.readdirSync(logsDir)
    .filter(f => f.endsWith('.log') || f.endsWith('.csv') || f.endsWith('.json'))
    .sort()
    .reverse();

  res.json({ files });
});

// Read a specific log file
app.get('/api/logs/:filename', (req, res) => {
  const logsDir = path.join(__dirname, '../Statements/Logs');
  const filename = path.basename(req.params.filename); // prevent path traversal
  const filePath = path.join(logsDir, filename);

  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'File not found' });
  }

  const content = fs.readFileSync(filePath, 'utf8');
  res.json({ filename, content });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Dashboard running at http://localhost:${PORT}`);
});
