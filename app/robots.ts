import type { MetadataRoute } from "next";

const origin = process.env.SITE_ORIGIN || "https://fiv-ai-news.vercel.app";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: `${origin}/sitemap.xml`,
  };
}
