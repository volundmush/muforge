from passlib.context import CryptContext

crypt_context = CryptContext(
    schemes=["argon2", "sha512_crypt", "plaintext"],
    deprecated=["sha512_crypt", "plaintext"],
)