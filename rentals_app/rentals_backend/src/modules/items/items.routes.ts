import { Router, Request, Response } from 'express';
import prisma from '../../config/db.js';
import { requireAuth } from '../../middleware/auth.js';
import { validateAttributes } from '../../utils/schemaValidator.js';
import { encrypt } from '../../utils/crypto.js';

const router = Router();

// Helper functions for distance sorting
const deg2rad = (deg: number): number => deg * (Math.PI / 180);

const calculateDistance = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
  const R = 6371; // Radius of the Earth in km
  const dLat = deg2rad(lat2 - lat1);
  const dLon = deg2rad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(deg2rad(lat1)) * Math.cos(deg2rad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c; // Distance in km
};

// GET /api/v1/rentals/items - Retrieve and filter items
router.get('/', async (req: Request, res: Response) => {
  const { categoryId, search, latitude, longitude, maxDistance } = req.query;

  try {
    const whereClause: any = {};

    if (categoryId) {
      whereClause.categoryId = categoryId as string;
    }

    if (search) {
      whereClause.OR = [
        { title: { contains: search as string, mode: 'insensitive' } },
        { description: { contains: search as string, mode: 'insensitive' } },
        { locationName: { contains: search as string, mode: 'insensitive' } },
      ];
    }

    // Retrieve items from database
    let items = await prisma.item.findMany({
      where: whereClause,
      include: {
        category: {
          select: { name: true, icon: true },
        },
      },
      orderBy: { createdAt: 'desc' },
    });

    // Handle Geographical Proximity filter and sorting if coordinates are supplied
    if (latitude && longitude) {
      const userLat = parseFloat(latitude as string);
      const userLon = parseFloat(longitude as string);

      if (!isNaN(userLat) && !isNaN(userLon)) {
        // Calculate distances
        let itemsWithDistance = items.map((item: any) => {
          const distance = calculateDistance(userLat, userLon, item.latitude, item.longitude);
          return { ...item, distance: parseFloat(distance.toFixed(2)) };
        });

        // Filter by max distance if specified
        if (maxDistance) {
          const maxD = parseFloat(maxDistance as string);
          if (!isNaN(maxD)) {
            itemsWithDistance = itemsWithDistance.filter((item: any) => item.distance <= maxD);
          }
        }

        // Sort by closest distance first
        itemsWithDistance.sort((a: any, b: any) => a.distance - b.distance);
        return res.json(itemsWithDistance);
      }
    }

    return res.json(items);
  } catch (error: any) {
    console.error('Error fetching items:', error);
    return res.status(500).json({ message: 'Internal server error while retrieving items.' });
  }
});

// POST /api/v1/rentals/items - List an item for rent
router.post('/', requireAuth, async (req: Request, res: Response) => {
  const user = req.user!;
  const {
    title,
    description,
    categoryId,
    attributes,
    locationName,
    latitude,
    longitude,
    pricePerDay,
    isDigital,
    credentialData, // Needed only if isDigital is true
    accessInstructions, // Needed only if isDigital is true
  } = req.body;

  // Validate core fields
  if (!title || !description || !categoryId || !locationName || pricePerDay === undefined) {
    return res.status(400).json({ message: 'Missing required listing parameters.' });
  }

  const latNum = parseFloat(latitude);
  const lonNum = parseFloat(longitude);
  const priceNum = parseFloat(pricePerDay);

  if (isNaN(latNum) || isNaN(lonNum) || isNaN(priceNum)) {
    return res.status(400).json({ message: 'Coordinates and price must be valid numeric values.' });
  }

  try {
    // 1. Fetch category schema definition
    const category = await prisma.itemCategory.findUnique({
      where: { id: categoryId },
    });

    if (!category) {
      return res.status(404).json({ message: 'Category not found.' });
    }

    // 2. Validate user-submitted dynamic attributes against category schema
    const validationResult = validateAttributes(category.schema, attributes || {});
    if (!validationResult.valid) {
      return res.status(400).json({
        message: 'Attributes validation failed.',
        errors: validationResult.errors,
      });
    }

    // 3. For Digital credentials, validate credentials properties
    if (isDigital) {
      if (!credentialData || !accessInstructions) {
        return res.status(400).json({
          message: 'Digital credentials require credential data and access instructions.',
        });
      }
    }

    // 4. Perform creation inside a database transaction to ensure Atomicity
    const newItem = await prisma.$transaction(async (tx: any) => {
      // Create primary Item entry
      const item = await tx.item.create({
        data: {
          title,
          description,
          categoryId,
          ownerId: user.id,
          ownerUsername: user.email.split('@')[0], // Extract username from email
          attributes: validationResult.cleanedAttributes,
          locationName,
          latitude: latNum,
          longitude: lonNum,
          pricePerDay: priceNum,
          isDigital: !!isDigital,
        },
      });

      // Write credentials if designated as digital
      if (isDigital) {
        // Symmetrically encrypt credential JSON data
        const secretString = typeof credentialData === 'string' ? credentialData : JSON.stringify(credentialData);
        const encryptedData = encrypt(secretString);

        await tx.digitalCredential.create({
          data: {
            itemId: item.id,
            credentialData: encryptedData,
            accessInstructions,
          },
        });
      }

      return item;
    });

    return res.status(201).json(newItem);
  } catch (error: any) {
    console.error('Error listing item:', error);
    return res.status(500).json({ message: 'Internal server error while creating listing.' });
  }
});

export default router;
