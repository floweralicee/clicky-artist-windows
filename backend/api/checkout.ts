import type { VercelRequest, VercelResponse } from '@vercel/node'
import { createClient } from '@supabase/supabase-js'
import Stripe from 'stripe'

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const authorization = req.headers.authorization
    if (!authorization?.startsWith('Bearer ')) {
      return res.status(401).json({ error: 'Missing auth token' })
    }

    const supabaseUrl = process.env.SUPABASE_URL
    const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
    if (!supabaseUrl || !supabaseServiceRoleKey) {
      return res.status(500).json({ error: 'Supabase is not configured' })
    }

    const supabaseAdmin = createClient(supabaseUrl, supabaseServiceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    })

    const token = authorization.slice('Bearer '.length).trim()
    const { data, error: authError } = await supabaseAdmin.auth.getUser(token)
    if (authError || !data.user) {
      return res.status(401).json({ error: 'Invalid auth token' })
    }

    const userId = data.user.id

    const stripeSecretKey = process.env.STRIPE_SECRET_KEY
    const stripePriceId = process.env.STRIPE_PRICE_ID
    if (!stripeSecretKey || !stripePriceId) {
      return res.status(500).json({ error: 'Stripe is not configured' })
    }

    const stripe = new Stripe(stripeSecretKey)
    const session = await stripe.checkout.sessions.create({
      mode: 'subscription',
      line_items: [{ price: stripePriceId, quantity: 1 }],
      client_reference_id: userId,
      metadata: { user_id: userId },
      subscription_data: {
        metadata: { user_id: userId },
      },
      success_url: 'https://floweralice.me/clicky?checkout=success',
      cancel_url: 'https://floweralice.me/clicky?checkout=cancelled',
    })

    if (!session.url) {
      return res.status(500).json({ error: 'Stripe did not return a checkout URL' })
    }

    return res.status(200).json({ url: session.url })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Could not start checkout'
    return res.status(500).json({ error: message })
  }
}
