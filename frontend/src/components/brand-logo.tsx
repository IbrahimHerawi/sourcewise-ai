import Image from "next/image";

import { cn } from "@/lib/utils";

const BRAND_ASSETS = {
  lockup: {
    height: 315,
    src: "/brand/sourcewise-lockup.png",
    width: 1393,
  },
  mark: {
    height: 1024,
    src: "/brand/sourcewise-mark.png",
    width: 1024,
  },
} as const;

type BrandLogoProps = {
  alt?: string;
  className?: string;
  priority?: boolean;
  sizes?: string;
  variant?: keyof typeof BRAND_ASSETS;
};

export function BrandLogo({
  alt = "SourceWise",
  className,
  priority = false,
  sizes,
  variant = "lockup",
}: BrandLogoProps) {
  const asset = BRAND_ASSETS[variant];

  return (
    <Image
      alt={alt}
      className={cn("object-contain", className)}
      height={asset.height}
      priority={priority}
      sizes={sizes}
      src={asset.src}
      width={asset.width}
    />
  );
}
