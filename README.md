# peepshow

### Video setup
Get a camera running on raspberry pi:

```
$ mkdir /tmp/stream
$ raspistill --nopreview -w 640 -h 480 -q 5 -o /tmp/stream/pic.jpg -tl 100 -t 9999999 -th 0:0:0 &
```
We are using timelapse mode (`-tl`) where a shot is taken every 100 ms. `-q` is for jpeg quality `<0-100>`. `-t` is timeout, also in ms. `-th` is `dimensions:quality` of thumbnail to be inserted into output jpg.

Optional: Add `-vf` and `-hf` to flip the image vertically and horizontally. 

Turn captured images into a web stream:
```
$ LD_LIBRARY_PATH=/usr/local/lib mjpg_streamer -i "input_file.so -f /tmp/stream -n pic.jpg" -o "output_http.so -w /usr/local/www"
```

### Create a tunnel from web to the live stream

raspberry pi:
```
$ autossh -M 65500 -o "ExitOnForwardFailure yes" -o "ServerAliveInterval 60" -o "ServerAliveCountMax 3" -o "StrictHostKeyChecking=no" -R 10010:localhost:8080 root@45.76.1.186
```
web server:
```
$ ssh -p 10010 pi@localhost
```
