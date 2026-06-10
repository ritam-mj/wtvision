import { Router, Request, Response } from 'express';
import prisma from '../../config/db.js';
import { requireAuth } from '../../middleware/auth.js';

const router = Router();

// GET /api/v1/rentals/bookings/my-rentals - Get bookings rented by the active user
router.get('/my-rentals', requireAuth, async (req: Request, res: Response) => {
  const user = req.user!;
  try {
    const bookings = await prisma.booking.findMany({
      where: { renterId: user.id },
      include: {
        item: true,
      },
      orderBy: { startDate: 'desc' },
    });
    return res.json(bookings);
  } catch (error: any) {
    console.error('Error fetching user rentals:', error);
    return res.status(500).json({ message: 'Internal server error while fetching bookings.' });
  }
});

// GET /api/v1/rentals/bookings/my-listings - Get bookings for items owned by the active user
router.get('/my-listings', requireAuth, async (req: Request, res: Response) => {
  const user = req.user!;
  try {
    const bookings = await prisma.booking.findMany({
      where: {
        item: { ownerId: user.id },
      },
      include: {
        item: true,
      },
      orderBy: { startDate: 'desc' },
    });
    return res.json(bookings);
  } catch (error: any) {
    console.error('Error fetching user listings bookings:', error);
    return res.status(500).json({ message: 'Internal server error while fetching bookings.' });
  }
});

// POST /api/v1/rentals/bookings - Book an item for a specific period
router.post('/', requireAuth, async (req: Request, res: Response) => {
  const user = req.user!;
  const { itemId, startDate, endDate } = req.body;

  if (!itemId || !startDate || !endDate) {
    return res.status(400).json({ message: 'Item ID, start date, and end date are required.' });
  }

  const start = new Date(startDate);
  const end = new Date(endDate);

  if (isNaN(start.getTime()) || isNaN(end.getTime())) {
    return res.status(400).json({ message: 'Invalid start or end date format.' });
  }

  if (start >= end) {
    return res.status(400).json({ message: 'Start date must be strictly before end date.' });
  }

  try {
    // 1. Verify item exists and is not owned by the renter
    const item = await prisma.item.findUnique({
      where: { id: itemId },
    });

    if (!item) {
      return res.status(404).json({ message: 'Item not found.' });
    }

    if (item.ownerId === user.id) {
      return res.status(400).json({ message: 'You cannot rent your own item.' });
    }

    // 2. Query for conflicting active bookings (overlapping periods)
    const conflicts = await prisma.booking.findFirst({
      where: {
        itemId: itemId,
        status: { in: ['pending', 'active'] },
        AND: [
          { startDate: { lte: end } },
          { endDate: { gte: start } },
        ],
      },
    });

    if (conflicts) {
      return res.status(400).json({
        message: 'This item is already booked during the selected timeframe.',
      });
    }

    // 3. Create the booking (default to 'active' status for prototyping)
    const booking = await prisma.booking.create({
      data: {
        itemId,
        renterId: user.id,
        renterUsername: user.email.split('@')[0],
        startDate: start,
        endDate: end,
        status: 'active', // Auto-active for simple prototype logic
      },
    });

    return res.status(201).json(booking);
  } catch (error: any) {
    console.error('Error creating booking:', error);
    return res.status(500).json({ message: 'Internal server error while creating booking.' });
  }
});

export default router;
