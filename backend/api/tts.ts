import type { VercelRequest, VercelResponse } from '@vercel/node'
import { createClient } from '@supabase/supabase-js'

const ELEVENLABS_MODEL_ID = 'eleven_flash_v2_5'

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

    const { text } = req.body ?? {}
    if (!text || typeof text !== 'string') {
      return res.status(400).json({ error: 'Text is required' })
    }

    const elevenLabsApiKey = process.env.ELEVENLABS_API_KEY
    const elevenLabsVoiceId = process.env.ELEVENLABS_VOICE_ID
    if (!elevenLabsApiKey || !elevenLabsVoiceId) {
      return res.status(500).json({ error: 'ElevenLabs is not configured' })
    }

    const response = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${elevenLabsVoiceId}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'xi-api-key': elevenLabsApiKey,
        },
        body: JSON.stringify({
          text,
          model_id: ELEVENLABS_MODEL_ID,
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.75,
          },
        }),
      },
    )

    if (!response.ok) {
      const errorBody = await response.text()
      return res.status(502).json({ error: `ElevenLabs request failed: ${errorBody.slice(0, 200)}` })
    }

    const audio = Buffer.from(await response.arrayBuffer())
    res.setHeader('Content-Type', 'audio/mpeg')
    return res.status(200).send(audio)
  } catch {
    return res.status(500).json({ error: 'Could not create audio' })
  }
}
