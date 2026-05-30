import type { VercelRequest, VercelResponse } from '@vercel/node'

import { HttpError, verifyJWT } from '../lib/auth'
import { getUsage } from '../lib/usage'

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const { user_id } = await verifyJWT(req)
    const usage = await getUsage(user_id)

    return res.status(200).json({
      subscription_status: usage.subscription_status,
      remaining_uses: usage.remaining,
      is_paid: usage.is_paid,
      limit: usage.limit,
      used: usage.count,
    })
  } catch (error) {
    if (error instanceof HttpError) {
      return res.status(error.statusCode).json({ error: error.message })
    }
    return res.status(500).json({ error: 'Could not check account status' })
  }
}

