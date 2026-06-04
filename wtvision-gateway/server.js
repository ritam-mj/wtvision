// wtvision-gateway/server.js
import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';
import jwt from 'jsonwebtoken';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 80;

// Load the Public Key to cryptographically verify incoming JWTs (signed by Auth Microservice)
const publicKey = fs.readFileSync(path.join(__dirname, 'public.pem'), 'utf8');

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

// 2. Gateway Router Rules

// A. Route Authentication endpoints directly (bypass authentication check)
app.use(
    '/auth',
    createProxyMiddleware({
        target: 'http://jwt_authservice:8001', // Auth Microservice
        changeOrigin: true,
        pathRewrite: {
            '^/auth': '', // Rewrites /auth/login to /login downstream
        },
    })
);

// B. Route Public Resource endpoints (bypass authentication check)
app.use(
    '/api/public',
    createProxyMiddleware({
        target: 'http://wtvisionbe:8000', // Django Backend
        changeOrigin: true,
    })
);

// C. Route Protected Resource endpoints (REQUIRE gateway authentication)
app.use(
    '/api/v1',
    authenticateGateway, // Runs authentication at the edge!
    createProxyMiddleware({
        target: 'http://wtvisionbe:8000', // Django Backend
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
