
<!-- restart services  -->
# Reload systemd
sudo systemctl daemon-reload

# Restart Gunicorn
sudo systemctl restart gunicorn

# Restart Nginx
sudo systemctl restart nginx



<!-- logs check-->
# Check Gunicorn logs
sudo journalctl -u gunicorn -n 50

# Check Nginx error logs
sudo tail -f /var/log/nginx/error.log   

# check all activity
systemctl list-units --type=service

# reload all deamon
sudo systemctl daemon-reload

# live logs check
journalctl -u gunicorn -f

# gunicor start
sudo systemctl start gunicorn

# gunicorn status
sudo systemctl start gunicorn


<!-- system restart cmd  -->
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# docs to pdf converte  
## first install
pip install python-docx Pillow pdf2image

# window 
pip install python-docx pywin32 Pillow
# Ubuntu/Debian
sudo apt-get install libreoffice    
