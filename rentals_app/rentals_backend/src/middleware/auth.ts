import { Request, Response, NextFunction } from 'express';

export interface AuthenticatedUser {
  id: string;
  email: string;
  role: string;
}

// Extend Express Request interface to include our user object
declare global {
  namespace Express {
    interface Request {
      user?: AuthenticatedUser;
    }
  }
}

export const requireAuth = (req: Request, res: Response, next: NextFunction) => {
  const userId = req.headers['x-user-id'] as string;
  const userEmail = req.headers['x-user-email'] as string;
  const userRole = req.headers['x-user-role'] as string;

  if (!userId) {
    return res.status(401).json({ message: 'Unauthorized. Gateway authentication missing.' });
  }

  req.user = {
    id: userId,
    email: userEmail || '',
    role: userRole || 'user',
  };

  next();
};
