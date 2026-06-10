import crypto from 'crypto';

const ALGORITHM = 'aes-256-cbc';
const IV_LENGTH = 16; // For AES, this is always 16

const getEncryptionKey = (): Buffer => {
  const hexKey = process.env.ENCRYPTION_KEY;
  if (!hexKey) {
    throw new Error('ENCRYPTION_KEY environment variable is not defined.');
  }
  
  const key = Buffer.from(hexKey, 'hex');
  if (key.length !== 32) {
    throw new Error('ENCRYPTION_KEY must be exactly 32 bytes (64 hex characters).');
  }
  
  return key;
};

/**
 * Encrypts a plaintext string.
 * Returns formatted string: 'iv_in_hex:encrypted_data_in_hex'
 */
export const encrypt = (text: string): string => {
  const key = getEncryptionKey();
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  
  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  
  return `${iv.toString('hex')}:${encrypted}`;
};

/**
 * Decrypts a formatted encrypted string ('iv:encrypted_data').
 * Returns original plaintext string.
 */
export const decrypt = (encryptedText: string): string => {
  const key = getEncryptionKey();
  const parts = encryptedText.split(':');
  
  if (parts.length !== 2) {
    throw new Error('Invalid encrypted text format. Expected "iv:ciphertext".');
  }
  
  const iv = Buffer.from(parts[0], 'hex');
  const encrypted = Buffer.from(parts[1], 'hex');
  
  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
  let decrypted = decipher.update(encrypted.toString('binary'), 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  
  return decrypted;
};
