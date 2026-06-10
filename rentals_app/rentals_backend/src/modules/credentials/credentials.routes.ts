import { Router, Request, Response } from 'express';
import prisma from '../../config/db.js';
import { requireAuth } from '../../middleware/auth.js';
import { decrypt } from '../../utils/crypto.js';

const router = Router();

// GET /api/v1/rentals/bookings/:id/credential - Retrieve active digital credentials
router.get('/bookings/:id/credential', requireAuth, async (req: Request, res: Response) => {
  const user = req.user!;
  const bookingId = req.params.id;
  const accessTokenHeader = req.headers['x-access-token'] || req.query.access_token;

  if (!accessTokenHeader) {
    return res.status(400).json({ message: 'Access token is required to view credentials.' });
  }

  try {
    // 1. Fetch booking with the associated item and its digital credential
    const booking = await prisma.booking.findUnique({
      where: { id: bookingId },
      include: {
        item: {
          include: {
            credential: true,
          },
        },
      },
    });

    if (!booking) {
      return res.status(404).json({ message: 'Booking not found.' });
    }

    const { item } = booking;

    // 2. Verify it is a digital item and contains credentials
    if (!item.isDigital || !item.credential) {
      return res.status(400).json({ message: 'This booking does not contain digital credentials.' });
    }

    // 3. Authenticate ownership: Renter must be the request user
    if (booking.renterId !== user.id) {
      return res.status(403).json({ message: 'Forbidden. You are not the renter of this item.' });
    }

    // 4. Validate Access Token matches the booking's generated token
    if (booking.accessToken !== accessTokenHeader) {
      return res.status(403).json({ message: 'Invalid credentials access token.' });
    }

    // 5. Enforce Lease Tenure time validation
    const now = new Date();
    if (booking.status !== 'active') {
      return res.status(403).json({ message: 'Booking status is not active.' });
    }

    if (now < booking.startDate) {
      return res.status(403).json({
        message: 'Rental tenure has not started yet.',
        startDate: booking.startDate,
      });
    }

    if (now > booking.endDate) {
      return res.status(403).json({
        message: 'Rental tenure has expired.',
        endDate: booking.endDate,
      });
    }

    // 6. Decrypt credential payload
    try {
      const decryptedDataString = decrypt(item.credential.credentialData);
      
      // Parse JSON structure if possible, otherwise return string
      let credentialsPayload;
      try {
        credentialsPayload = JSON.parse(decryptedDataString);
      } catch {
        credentialsPayload = decryptedDataString;
      }

      return res.json({
        itemId: item.id,
        itemTitle: item.title,
        credentials: credentialsPayload,
        accessInstructions: item.credential.accessInstructions,
        tenureRemainingSeconds: Math.max(0, Math.floor((booking.endDate.getTime() - now.getTime()) / 1000)),
      });
    } catch (decryptErr) {
      console.error('Decryption failure:', decryptErr);
      return res.status(500).json({ message: 'Failed to decrypt secure credential data.' });
    }
  } catch (error: any) {
    console.error('Error fetching credentials:', error);
    return res.status(500).json({ message: 'Internal server error while retrieving credentials.' });
  }
});

export default router;
