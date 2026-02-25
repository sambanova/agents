const ENCRYPTION_KEY_NAME = 'app_encryption_key'

// Generate or retrieve the AES-256-GCM encryption key
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

// Encrypt a string using AES-256-GCM with a random IV
export const encryptKey = async (key) => {
  const cryptoKey = await getEncryptionKey()
  const iv = window.crypto.getRandomValues(new Uint8Array(12))
  const encoded = new TextEncoder().encode(key)
  const encrypted = await window.crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    cryptoKey,
    encoded
  )
  // Prepend IV to ciphertext, encode as base64 for storage
  const combined = new Uint8Array(iv.length + encrypted.byteLength)
  combined.set(iv)
  combined.set(new Uint8Array(encrypted), iv.length)
  return btoa(String.fromCharCode(...combined))
}

// Decrypt a string using AES-256-GCM
// Falls back to plain base64 decode for backward compatibility with old stored keys
export const decryptKey = async (encryptedKey) => {
  try {
    const cryptoKey = await getEncryptionKey()
    const combined = Uint8Array.from(atob(encryptedKey), c => c.charCodeAt(0))
    const iv = combined.slice(0, 12)
    const ciphertext = combined.slice(12)
    const decrypted = await window.crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      cryptoKey,
      ciphertext
    )
    return new TextDecoder().decode(decrypted)
  } catch {
    // Backward compatibility: old keys stored as plain base64
    try {
      return atob(encryptedKey)
    } catch {
      return encryptedKey
    }
  }
}
