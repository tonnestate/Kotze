"""Read "<quantity> <unit_price_cents>" lines from stdin, print one total per line."""
import sys

from app.pricing import total_cents


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        quantity, price = (int(part) for part in line.split())
        print(total_cents(quantity, price))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
