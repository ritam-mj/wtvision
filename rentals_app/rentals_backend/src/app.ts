import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import categoriesRouter from './modules/categories/categories.routes.js';
import itemsRouter from './modules/items/items.routes.js';
import bookingsRouter from './modules/bookings/bookings.routes.js';
import credentialsRouter from './modules/credentials/credentials.routes.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

// Configure CORS (allow API Gateway on port 80 and frontend dev servers on port 3000 and 3001)
app.use(
  cors({
    origin: ['http://localhost', 'http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:3001', 'http://127.0.0.1:3001'],
    credentials: true,
  })
);

app.use(express.json());

// Logger middleware for debugging gateway headers
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  if (req.headers['x-user-id']) {
    console.log(`  User: ${req.headers['x-user-email']} (${req.headers['x-user-id']})`);
  } else {
    console.log('  User: Unauthenticated (No Gateway Headers)');
  }
  next();
});

// Mount domain routes
app.use('/api/v1/rentals/categories', categoriesRouter);
app.use('/api/v1/rentals/items', itemsRouter);
app.use('/api/v1/rentals/bookings', bookingsRouter);
app.use('/api/v1/rentals', credentialsRouter); // Mounts /bookings/:id/credential under /api/v1/rentals/bookings/:id/credential

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'OK', service: 'rentals-backend' });
});

// Start Express Server
app.listen(PORT, () => {
  console.log(`🚀 Rentals Backend service is running on port ${PORT}`);
});
