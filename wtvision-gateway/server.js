// wtvision-gateway/server.js
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import jwt from 'jsonwebtoken';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import rateLimit from 'express-rate-limit';
import RedisStore from 'rate-limit-redis';
import { Redis } from 'ioredis';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 80;

// Enable CORS at the API Gateway level to support multiple frontend origins (port 3000 and 3001)
app.use((req, res, next) => {
    const origin = req.headers.origin;
    if (origin && (origin.startsWith('http://localhost') || origin.startsWith('http://127.0.0.1'))) {
        res.setHeader('Access-Control-Allow-Origin', origin);
    }
    res.setHeader('Access-Control-Allow-Credentials', 'true');
    res.setHeader('Access-Control-Allow-Methods', 'GET,HEAD,PUT,PATCH,POST,DELETE,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, x-access-token');

    // Instantly intercept preflight OPTIONS requests at the edge
    if (req.method === 'OPTIONS') {
        return res.sendStatus(204);
    }
    next();
});

// Load the Public Key to cryptographically verify incoming JWTs (signed by Auth Microservice)
const publicKey = fs.readFileSync(path.join(__dirname, 'public.pem'), 'utf8');

// Initialize Redis client
const redisClient = new Redis({
    host: process.env.REDIS_HOST || 'redis',
    port: 6379,
});

redisClient.on('error', (err) => {
    console.error('Redis error:', err);
});

// Configure Rate Limiters
const apiLimiter = rateLimit({
    store: new RedisStore({
        sendCommand: (...args) => redisClient.call(...args),
    }),
    windowMs: 1 * 60 * 1000, // 1 minute
    max: 100, // Limit each IP to 100 requests per minute
    message: { message: 'Too many requests from this IP, please try again after a minute.' },
    standardHeaders: true,
    legacyHeaders: false,
});

const authLimiter = rateLimit({
    store: new RedisStore({
        sendCommand: (...args) => redisClient.call(...args),
    }),
    windowMs: 1 * 60 * 1000, // 1 minute
    max: 20, // Strict limit for auth endpoints
    message: { message: 'Too many login attempts, please try again after a minute.' },
    standardHeaders: true,
    legacyHeaders: false,
});

// 1. JWT Authentication Middleware for Gateway
const authenticateGateway = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) {
        return res.status(401).json({ message: 'Access Token Required' });
    }

    // Verify the JWT signature using the asymmetric public key
    jwt.verify(token, publicKey, { algorithms: ['RS256'] }, (err, decoded) => {
        if (err) {
            return res.status(403).json({ message: 'Invalid or Expired Token' });
        }

        // Inject decrypted user claims into headers to be forwarded downstream
        req.headers['x-user-id'] = decoded.user_id;
        req.headers['x-user-email'] = decoded.email;
        req.headers['x-user-role'] = decoded.role || 'user';

        next();
    });
};

// 1B. Optional JWT Authentication Middleware for Gateway (allows public endpoints downstream)
const authenticateGatewayOptional = (req, res, next) => {
    const authHeader = req.headers['authorization'];
    const token = authHeader && authHeader.split(' ')[1];

    if (!token) {
        return next();
    }

    jwt.verify(token, publicKey, { algorithms: ['RS256'] }, (err, decoded) => {
        if (err) {
            return res.status(403).json({ message: 'Invalid or Expired Token' });
        }

        req.headers['x-user-id'] = decoded.user_id;
        req.headers['x-user-email'] = decoded.email;
        req.headers['x-user-role'] = decoded.role || 'user';
        next();
    });
};

// 2. Gateway Router Rules

// A. Route Authentication endpoints directly (bypass authentication check)
app.use(
    '/auth',
    authLimiter,
    createProxyMiddleware({
        target: 'http://jwt_authservice:8001', // Auth Microservice
        changeOrigin: true,
        pathRewrite: {
            '^/auth': '', // Rewrites /auth/login to /login downstream
        },
    })
);

const BACKEND_URL = process.env.BACKEND_URL || 'http://wtvisionbe:8000';
const RENTALS_BACKEND_URL = process.env.RENTALS_BACKEND_URL || 'http://localhost:5000';

// B. Route Public Resource endpoints (bypass authentication check)
app.use(
    '/api/public',
    apiLimiter,
    createProxyMiddleware({
        target: BACKEND_URL,
        changeOrigin: true,
    })
);

// B2. Route Rentals API endpoints (with optional authentication verification at the edge)
app.use(
    '/api/v1/rentals',
    apiLimiter,
    authenticateGatewayOptional,
    createProxyMiddleware({
        target: RENTALS_BACKEND_URL,
        changeOrigin: true,
        pathRewrite: (path, req) => {
            return '/api/v1/rentals' + path;
        },
        onProxyReq: (proxyReq, req) => {
            if (req.headers['x-user-id']) {
                proxyReq.setHeader('X-User-Id', req.headers['x-user-id']);
                proxyReq.setHeader('X-User-Email', req.headers['x-user-email']);
                proxyReq.setHeader('X-User-Role', req.headers['x-user-role']);
            }
            proxyReq.removeHeader('Authorization');
        },
    })
);

// C. Route Protected Resource endpoints (REQUIRE gateway authentication)
app.use(
    '/api/v1',
    apiLimiter,
    authenticateGateway, // Runs authentication at the edge!
    createProxyMiddleware({
        target: BACKEND_URL,
        changeOrigin: true,
        onProxyReq: (proxyReq, req) => {
            // Forward the injected user identity headers to downstream service
            proxyReq.setHeader('X-User-Id', req.headers['x-user-id']);
            proxyReq.setHeader('X-User-Email', req.headers['x-user-email']);
            proxyReq.setHeader('X-User-Role', req.headers['x-user-role']);

            // Clean/Strip the original Authorization header so downstream services 
            // don't try to parse it again
            proxyReq.removeHeader('Authorization');
        },
    })
);


app.listen(PORT, () => {
    console.log(`🚀 API Gateway running on port ${PORT}`);
});
