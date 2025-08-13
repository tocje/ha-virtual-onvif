ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-dev \
    gcc \
    musl-dev \
    libxml2-dev \
    libxslt-dev \
    linux-headers

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY rootfs/ /

# Make run script executable
RUN chmod a+x /usr/bin/run.sh

# Create necessary directories
RUN mkdir -p /app/config \
    /app/templates \
    /app/static \
    /var/log/virtual-onvif

# Set up logging
RUN touch /var/log/virtual-onvif/app.log

# Expose ports
EXPOSE 8080 8081 8082 3702/udp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["/usr/bin/run.sh"]