import { PrismaClient } from '@prisma/client';
import dotenv from 'dotenv';
import path from 'path';
import fs from 'fs';

// Load the root .env file if it exists to retrieve ADMIN_PASSWORD dynamically
const rootEnvPath = path.resolve(process.cwd(), '../../.env');
if (fs.existsSync(rootEnvPath)) {
  const rootEnv = dotenv.parse(fs.readFileSync(rootEnvPath));
  if (rootEnv.ADMIN_PASSWORD) {
    process.env.ADMIN_PASSWORD = rootEnv.ADMIN_PASSWORD;
  }
}

// Dynamically replace the password in DATABASE_URL if ADMIN_PASSWORD is set
if (process.env.DATABASE_URL && process.env.ADMIN_PASSWORD) {
  process.env.DATABASE_URL = process.env.DATABASE_URL.replace(
    /(postgresql:\/\/[^:]+:)([^@]+)(@.+)/,
    `$1${process.env.ADMIN_PASSWORD}$3`
  );
}

const prisma = new PrismaClient({
  log: process.env.NODE_ENV === 'development' ? ['query', 'info', 'warn', 'error'] : ['error'],
});

export default prisma;
