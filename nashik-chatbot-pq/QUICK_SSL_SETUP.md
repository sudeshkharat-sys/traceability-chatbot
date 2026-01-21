# Quick SSL Setup Reference

## 🚀 Fastest Way to Setup SSL

```bash
cd ~/Traceability/nashik-chatbot-pq

# Run the automated setup script
sudo ./setup-ssl.sh /home/maiuser/certificate

# Restart Docker
sudo docker compose down && sudo docker compose up -d

# Test HTTPS
curl https://localhost --insecure
```

That's it! The script handles everything automatically.

---

## 📋 What You Have

Your SSL certificate files (in `/home/maiuser/certificate/` or wherever they are):
- **m-devsecops.com.cer** (or .crt) - Your SSL certificate
- **m-devsecops.key** - Your private key
- **m-devsecops.pfx** - PFX bundle (contains cert + key together)
- **CloudflareCA.cer** - CA certificate for the certificate chain

---

## 🎯 What You Need to Do

### Option 1: If Certificates Are in `/home/maiuser/certificate/`

```bash
cd ~/Traceability/nashik-chatbot-pq
sudo ./setup-ssl.sh /home/maiuser/certificate
sudo docker compose down && sudo docker compose up -d
```

### Option 2: If Certificates Are Somewhere Else

```bash
cd ~/Traceability/nashik-chatbot-pq

# Replace with your actual path
sudo ./setup-ssl.sh /path/to/your/certificates

sudo docker compose down && sudo docker compose up -d
```

### Option 3: Manual Copy (if script doesn't work)

```bash
cd ~/Traceability/nashik-chatbot-pq
mkdir -p ssl

# If using PFX file (easiest)
sudo openssl pkcs12 -in /path/to/m-devsecops.pfx -clcerts -nokeys -out ssl/cert.pem
sudo openssl pkcs12 -in /path/to/m-devsecops.pfx -nocerts -nodes -out ssl/key.pem

# Add CA certificate
sudo cat /path/to/CloudflareCA.cer >> ssl/cert.pem

# Set permissions
sudo chmod 600 ssl/key.pem
sudo chmod 644 ssl/cert.pem
sudo chown $USER:$USER ssl/*.pem

# Restart Docker
sudo docker compose down && sudo docker compose up -d
```

---

## ✅ Verify It's Working

```bash
# Test HTTPS
curl https://localhost --insecure

# Check Docker containers
sudo docker compose ps

# Check nginx logs (should have no SSL errors)
sudo docker compose logs nginx | grep -i ssl

# Check if port 443 is listening
sudo netstat -tulpn | grep 443
```

---

## 🔧 Common Issues

### Issue: "Could not read certificate"

**Fix:**
```bash
# Certificate might be in DER format - convert to PEM
openssl x509 -inform DER -in /path/to/cert.cer -out ssl/cert.pem
```

### Issue: "Permission denied"

**Fix:**
```bash
sudo chmod 600 ssl/key.pem
sudo chmod 644 ssl/cert.pem
sudo chown $USER:$USER ssl/*.pem
```

### Issue: "Certificate and key do not match"

**Fix:** Extract both from the same PFX file:
```bash
openssl pkcs12 -in cert.pfx -clcerts -nokeys -out ssl/cert.pem
openssl pkcs12 -in cert.pfx -nocerts -nodes -out ssl/key.pem
```

### Issue: Nginx container won't start

**Fix:**
```bash
# Check logs
sudo docker compose logs nginx

# Verify nginx config
sudo docker compose config

# Check if files exist
ls -la ssl/
```

---

## 📦 What's Already Configured

✅ nginx.conf - HTTP (port 80) and HTTPS (port 443) server blocks
✅ docker-compose.yml - Exposes ports 80 and 443
✅ docker-compose.yml - Mounts ./ssl directory to container
✅ .gitignore - SSL files won't be committed to git

**You only need to provide the certificate files!**

---

## 🌐 Load Balancer Setup

You mentioned having a load balancer. You have two options:

### Current Setup: End-to-End SSL ✅

```
Internet → LB:443 (HTTPS) → VM:443 (HTTPS) → App
```

- Load balancer has SSL certificate
- VM also has SSL certificate (this guide)
- Most secure (double encryption)

### Alternative: SSL Termination at LB Only

```
Internet → LB:443 (HTTPS) → VM:80 (HTTP) → App
```

- Only load balancer needs SSL certificate
- VM only uses HTTP (simpler)
- Less secure but simpler setup

**Current configuration supports end-to-end SSL.**

---

## 🎉 Success Checklist

- [ ] Certificate files in `/home/maiuser/certificate/` (or known location)
- [ ] Run setup script: `sudo ./setup-ssl.sh /path/to/certificates`
- [ ] See "Setup Complete" message
- [ ] Restart Docker: `sudo docker compose down && sudo docker compose up -d`
- [ ] All 4 containers running: `sudo docker compose ps`
- [ ] HTTPS responds: `curl https://localhost --insecure`
- [ ] Nginx logs clean: `sudo docker compose logs nginx`
- [ ] Test from browser: `https://your-vm-ip`
- [ ] Test through load balancer: `https://your-domain.com`

---

## 📚 More Details

For complete troubleshooting and detailed explanations, see:
- **CERTIFICATE_SETUP_GUIDE.md** - Comprehensive guide with all options
- **SSL_SETUP.md** - Complete SSL/HTTPS setup documentation
- **LOAD_BALANCER_SETUP.md** - Load balancer integration guide

---

## 🆘 Need Help?

If the automated script doesn't work:

1. Run it and share the output
2. Check if certificate files exist: `ls -la /home/maiuser/certificate/`
3. Try manual setup (Option 3 above)
4. Share error messages from: `sudo docker compose logs nginx`

Most issues are due to:
- Wrong certificate file path
- Certificate in wrong format (DER vs PEM)
- Permission issues
- Certificate and key mismatch
