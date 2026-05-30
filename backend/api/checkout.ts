import type { VercelRequest, VercelResponse } from '@vercel/node'
import Stripe from 'stripe'

import { HttpError, verifyJWT } from '../lib/auth'

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const { user_id } = await verifyJWT(req)

    const stripeSecretKey = process.env.STRIPE_SECRET_KEY
    const stripePriceId = process.env.STRIPE_PRICE_ID
    if (!stripeSecretKey || !stripePriceId) {
      return res.status(500).json({ error: 'Stripe is not configured' })
    }

    const stripe = new Stripe(stripeSecretKey)
    const session = await stripe.checkout.sessions.create({
      mode: 'subscription',
      line_items: [{ price: stripePriceId, quantity: 1 }],
      client_reference_id: user_id,
      metadata: { user_id },
      subscription_data: {
        metadata: { user_id },
      },
      success_url: 'https://floweralice.me/clicky?checkout=success',
      cancel_url: 'https://floweralice.me/clicky?checkout=cancelled',
    })

    if (!session.url) {
      return res.status(500).json({ error: 'Stripe did not return a checkout URL' })
    }

    return res.status(200).json({ url: session.url })
  } catch (error) {
    if (error instanceof HttpError) {
      return res.status(error.statusCode).json({ error: error.message })
    }
    return res.status(500).json({ error: 'Could not start checkout' })
  }
}
