import Image from "next/image";
import Link from "next/link";

export function Brand({ href = "/" }: { href?: string }) {
  return <Link className="brand brand-logo" href={href} aria-label="CLPZ home">
    <Image src="/logo.png" alt="CLPZ" width={147} height={36} priority />
  </Link>;
}
