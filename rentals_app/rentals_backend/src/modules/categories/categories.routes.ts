import { Router, Request, Response } from 'express';
import prisma from '../../config/db.js';
import { requireAuth } from '../../middleware/auth.js';

const router = Router();

// GET /api/v1/rentals/categories - List all categories
router.get('/', async (req: Request, res: Response) => {
  try {
    const categories = await prisma.itemCategory.findMany({
      orderBy: { name: 'asc' },
    });
    return res.json(categories);
  } catch (error: any) {
    console.error('Error fetching categories:', error);
    return res.status(500).json({ message: 'Internal server error while fetching categories.' });
  }
});

// POST /api/v1/rentals/categories - Create a new category
// For development/prototype purposes, this is open to authenticated users
router.post('/', requireAuth, async (req: Request, res: Response) => {
  const { name, icon, schema } = req.body;

  if (!name) {
    return res.status(400).json({ message: 'Category name is required.' });
  }

  try {
    // Validate schema format is an array
    if (schema && !Array.isArray(schema)) {
      return res.status(400).json({ message: 'Schema must be an array of field specifications.' });
    }

    const existingCategory = await prisma.itemCategory.findUnique({
      where: { name },
    });

    if (existingCategory) {
      return res.status(400).json({ message: 'Category with this name already exists.' });
    }

    const category = await prisma.itemCategory.create({
      data: {
        name,
        icon: icon || null,
        schema: schema || [],
      },
    });

    return res.status(201).json(category);
  } catch (error: any) {
    console.error('Error creating category:', error);
    return res.status(500).json({ message: 'Internal server error while creating category.' });
  }
});

export default router;
