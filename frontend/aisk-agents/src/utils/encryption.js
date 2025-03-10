const ENCRYPTION_KEY_NAME = 'app_encryption_key'

// Generate or retrieve the encryption key
const getEncryptionKey = async () => {
  try {
    // Try to get existing key
    const storedKey = sessionStorage.getItem(ENCRYPTION_KEY_NAME)
    if (storedKey) {
      const keyData = JSON.parse(storedKey)
      return await window.crypto.subtle.importKey(
        'jwk',
        keyData,
        { name: 'AES-GCM', length: 256 },
        true,
        ['encrypt', 'decrypt']
      )
    }

    // Generate new key if none exists
    const key = await window.crypto.subtle.generateKey(
      { name: 'AES-GCM', length: 256 },
      true,
      ['encrypt', 'decrypt']
    )

    // Store the key as JWK
    const keyData = await window.crypto.subtle.exportKey('jwk', key)
    sessionStorage.setItem(ENCRYPTION_KEY_NAME, JSON.stringify(keyData))
    return key
  } catch (error) {
    console.error('Error handling encryption key:', error)
    throw error
  }
}

// Simple encryption/decryption for demo purposes
// In production, use a more secure encryption method
export const encryptKey = async (key) => {
  // For demo, just using base64 encoding
  return btoa(key)
}

export const decryptKey = async (encryptedKey) => {
  // For demo, just using base64 decoding
  return atob(encryptedKey)
} 