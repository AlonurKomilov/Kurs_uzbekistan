/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  async rewrites() {
    // Use different API URL for container vs local development
    const apiUrl = process.env.NODE_ENV === 'production' || process.env.DOCKER_ENV
      ? 'http://api:8000'
      : 'http://localhost:8000';
    
    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`
      }
    ];
  },
}

module.exports = nextConfig