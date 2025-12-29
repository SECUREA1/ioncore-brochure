FROM node:20-alpine

WORKDIR /usr/src/app

# Install only the runtime dependencies
COPY package*.json ./
RUN npm install --production

# Copy the rest of the brochure library, including HTML assets
COPY . .

EXPOSE 3000

CMD ["npm", "start"]
