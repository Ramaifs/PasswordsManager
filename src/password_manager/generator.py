from dataclasses import dataclass
import secrets
import string

from .errors import VaultError


@dataclass(frozen=True)
class GeneratorOptions:
    length: int = 20
    count: int = 1
    lower: bool = True
    upper: bool = True
    digits: bool = True
    symbols: bool = True
    exclude_similar: bool = False


def generate(options: GeneratorOptions = GeneratorOptions()) -> list[str]:
    if type(options.length) is not int or not 8 <= options.length <= 128:
        raise VaultError("Длина должна быть от 8 до 128.")
    if type(options.count) is not int or not 1 <= options.count <= 100:
        raise VaultError("Количество должно быть от 1 до 100.")
    groups = [chars for enabled, chars in (
        (options.lower, string.ascii_lowercase), (options.upper, string.ascii_uppercase),
        (options.digits, string.digits), (options.symbols, "!@#$%^&*()-_=+[]{};:,.?/")
    ) if enabled]
    if options.exclude_similar:
        groups = ["".join(c for c in group if c not in "Il1O0o|") for group in groups]
    if not groups or not all(groups):
        raise VaultError("Выберите хотя бы одну непустую группу символов.")
    alphabet = "".join(groups)
    result = []
    for _ in range(options.count):
        # Rejection sampling preserves the uniform distribution conditional on all groups.
        while True:
            password = "".join(secrets.choice(alphabet) for _ in range(options.length))
            if all(any(c in group for c in password) for group in groups):
                result.append(password)
                break
    return result
