# Stage 1: Build the application
FROM node:18-alpine AS build

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install the dependencies
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Set environment variables for build
ARG VITE_API_URL
ARG VITE_CLERK_PUBLISHABLE_KEY
# ARG VITE_CLERK_FRONTEND_API
# ARG VITE_CLERK_DOMAIN

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY
# ENV VITE_CLERK_FRONTEND_API=$VITE_CLERK_FRONTEND_API
# ENV VITE_CLERK_DOMAIN=$VITE_CLERK_DOMAIN

# Build the application
RUN npm run build

# Stage 2: Serve the application
FROM nginx:alpine

# Install OpenSSL and gettext for envsubst
RUN apk add --no-cache openssl gettext

# Create SSL certificate directories
RUN mkdir -p /etc/nginx/ssl /etc/sn-certs/snova.ai

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy the built files from the previous stage
COPY --from=build /app/dist /usr/share/nginx/html

# Expose ports
EXPOSE 80 443

# Start Nginx when the container launches
CMD ["nginx", "-g", "daemon off;"] 