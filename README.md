# peepshow

Get a camera running on raspberry pi:

```
$ mkdir /tmp/stream
$ raspistill --nopreview -w 640 -h 480 -q 5 -o /tmp/stream/pic.jpg -tl 100 -t 9999999 -th 0:0:0 &
```
We are using timelapse mode (`-tl`) where a shot is taken every 100 ms. `-q` is for jpeg quality `<0-100>`. `-t` is timeout, also in ms. `-th` is `dimensions:quality` of thumbnail to be inserted into output jpg.

Optional: Add `-vf` and `-hf` to flip the image vertically and horizontally. 
