import type { VercelRequest, VercelResponse } from '@vercel/node'

import { HttpError, verifyJWT } from '../lib/auth'

const ELEVENLABS_MODEL_ID = 'eleven_flash_v2_5'

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    await verifyJWT(req)

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
      return res.status(502).json({ error: 'ElevenLabs request failed' })
    }

    const audio = Buffer.from(await response.arrayBuffer())
    res.setHeader('Content-Type', 'audio/mpeg')
    return res.status(200).send(audio)
  } catch (error) {
    if (error instanceof HttpError) {
      return res.status(error.statusCode).json({ error: error.message })
    }
    return res.status(500).json({ error: 'Could not create audio' })
  }
}

