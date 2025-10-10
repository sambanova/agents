/**
 * Audio handler utility for voice chat functionality.
 * Handles microphone capture, audio encoding, and playback.
 */

/**
 * Get user media stream from microphone
 * @returns {Promise<MediaStream>} Audio stream
 */
export async function getMicrophoneStream() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: 16000,
        channelCount: 1,
      },
    })
    return stream
  } catch (error) {
    console.error('Error accessing microphone:', error)
    throw new Error('Microphone access denied. Please enable microphone permissions.')
  }
}

/**
 * Create an audio recorder that captures and encodes audio
 * @param {MediaStream} stream - Audio stream from microphone
 * @param {Function} onDataAvailable - Callback for audio chunks
 * @returns {MediaRecorder} Configured media recorder
 */
export function createAudioRecorder(stream, onDataAvailable) {
  // Check for supported MIME types
  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : 'audio/webm'

  const recorder = new MediaRecorder(stream, {
    mimeType,
    audioBitsPerSecond: 128000,
  })

  // Capture audio chunks every 100ms for low latency
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0 && onDataAvailable) {
      onDataAvailable(event.data)
    }
  }

  return recorder
}

/**
 * Convert audio blob to base64 string
 * @param {Blob} blob - Audio blob
 * @returns {Promise<string>} Base64 encoded audio
 */
export async function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      const base64 = reader.result.split(',')[1]
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

/**
 * Audio playback queue manager
 */
export class AudioPlaybackQueue {
  constructor() {
    this.queue = []
    this.isPlaying = false
    this.currentAudio = null
    this.audioContext = null
    this.volume = 1.0
  }

  /**
   * Initialize Web Audio API context
   */
  async init() {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)()
    }
  }

  /**
   * Add audio to the playback queue
   * @param {string} base64Audio - Base64 encoded audio
   */
  async enqueue(base64Audio) {
    await this.init()
    this.queue.push(base64Audio)

    if (!this.isPlaying) {
      this.playNext()
    }
  }

  /**
   * Play the next audio in the queue
   */
  async playNext() {
    if (this.queue.length === 0) {
      this.isPlaying = false
      return
    }

    this.isPlaying = true
    const base64Audio = this.queue.shift()

    try {
      // Decode base64 to array buffer
      const binaryString = atob(base64Audio)
      const bytes = new Uint8Array(binaryString.length)
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i)
      }

      // Decode audio data
      const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer)

      // Create audio source
      const source = this.audioContext.createBufferSource()
      source.buffer = audioBuffer

      // Create gain node for volume control
      const gainNode = this.audioContext.createGain()
      gainNode.gain.value = this.volume

      // Connect nodes
      source.connect(gainNode)
      gainNode.connect(this.audioContext.destination)

      // Store reference to current audio
      this.currentAudio = source

      // Play audio
      source.start(0)

      // When finished, play next
      source.onended = () => {
        this.currentAudio = null
        this.playNext()
      }
    } catch (error) {
      console.error('Error playing audio:', error)
      // Continue to next audio on error
      this.playNext()
    }
  }

  /**
   * Stop current playback and clear queue
   */
  stop() {
    if (this.currentAudio) {
      try {
        this.currentAudio.stop()
      } catch (e) {
        // Audio might already be stopped
      }
      this.currentAudio = null
    }
    this.queue = []
    this.isPlaying = false
  }

  /**
   * Clear queue but let current audio finish
   */
  clearQueue() {
    this.queue = []
  }

  /**
   * Set playback volume
   * @param {number} volume - Volume level (0.0 to 1.0)
   */
  setVolume(volume) {
    this.volume = Math.max(0, Math.min(1, volume))
  }

  /**
   * Get queue length
   * @returns {number} Number of items in queue
   */
  getQueueLength() {
    return this.queue.length
  }
}

/**
 * Audio visualizer for showing audio levels
 */
export class AudioVisualizer {
  constructor(stream) {
    this.stream = stream
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)()
    this.analyser = this.audioContext.createAnalyser()
    this.analyser.fftSize = 256
    this.dataArray = new Uint8Array(this.analyser.frequencyBinCount)

    const source = this.audioContext.createMediaStreamSource(stream)
    source.connect(this.analyser)
  }

  /**
   * Get current audio level (0-100)
   * Uses time-domain data (waveform) for better voice activity detection
   * @returns {number} Audio level
   */
  getLevel() {
    this.analyser.getByteTimeDomainData(this.dataArray)

    // Calculate RMS (Root Mean Square) for better voice detection
    let sum = 0
    for (let i = 0; i < this.dataArray.length; i++) {
      const normalized = (this.dataArray[i] - 128) / 128 // Convert to -1 to 1 range
      sum += normalized * normalized
    }
    const rms = Math.sqrt(sum / this.dataArray.length)

    // Normalize to 0-100 and amplify for better sensitivity
    const level = Math.min(100, rms * 200)

    return Math.round(level)
  }

  /**
   * Get frequency data for waveform visualization
   * @returns {Uint8Array} Frequency data
   */
  getFrequencyData() {
    this.analyser.getByteFrequencyData(this.dataArray)
    return this.dataArray
  }

  /**
   * Clean up resources
   */
  cleanup() {
    if (this.audioContext) {
      this.audioContext.close()
    }
  }
}

/**
 * Check if browser supports required audio APIs
 * @returns {object} Support status
 */
export function checkAudioSupport() {
  return {
    mediaDevices: !!navigator.mediaDevices?.getUserMedia,
    mediaRecorder: typeof MediaRecorder !== 'undefined',
    audioContext: typeof (window.AudioContext || window.webkitAudioContext) !== 'undefined',
    webSocket: typeof WebSocket !== 'undefined',
  }
}

/**
 * Request microphone permissions
 * @returns {Promise<boolean>} Whether permission was granted
 */
export async function requestMicrophonePermission() {
  try {
    const stream = await getMicrophoneStream()
    // Stop the stream immediately, we just wanted to check permissions
    stream.getTracks().forEach(track => track.stop())
    return true
  } catch (error) {
    return false
  }
}
