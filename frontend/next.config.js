/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // NEXT_PUBLIC_BACKEND_URL is read at build time. On Vercel set it in
  // Project -> Settings -> Environment Variables (e.g. https://your-api.onrender.com).
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000',
  },
};

module.exports = nextConfig;
