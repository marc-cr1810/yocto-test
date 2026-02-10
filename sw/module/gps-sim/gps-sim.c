#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/random.h>
#include <linux/serial.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/timer.h>
#include <linux/tty.h>
#include <linux/tty_driver.h>
#include <linux/tty_flip.h>
#include <linux/uaccess.h>
#include <linux/version.h>

#define DRIVER_VERSION "v1.0"
#define DRIVER_AUTHOR "Yocto Workspace"
#define DRIVER_DESC "GPS Simulation TTY Driver"
#define GPS_TTY_MAJOR 240 /* Experimental range */
#define GPS_TTY_MINORS 1
#define GPS_TTY_NAME "ttyGPS"

MODULE_LICENSE("GPL");
MODULE_AUTHOR(DRIVER_AUTHOR);
MODULE_DESCRIPTION(DRIVER_DESC);

static struct tty_driver *gps_tty_driver;
static struct tty_port gps_tty_port;
static struct timer_list gps_timer;

/* State for simulation */
static int gps_hour = 12;
static int gps_min = 35;
static int gps_sec = 19;

/*
 * Base coordinates:
 * Lat: -35.315075 -> 35 degrees, 18.9045 minutes South
 * Lon: 149.129404 -> 149 degrees, 07.7642 minutes East
 */
static int lat_deg = 35;
static int lat_min_int = 18;
static int lat_min_frac = 9045; /* .9045 */

static int lon_deg = 149;
static int lon_min_int = 7;
static int lon_min_frac = 7642; /* .7642 */

/*
 * We need a way to pass data to the tty layer.
 * In a real device, an interrupt would trigger this.
 * Here, we use a timer.
 */

static unsigned char nmea_checksum(const char *s) {
  unsigned char c = 0;
  while (*s)
    c ^= *s++;
  return c;
}

static void gps_simulate_nmea(struct timer_list *t) {
  struct tty_struct *tty;
  struct tty_port *port = &gps_tty_port;
  char nmea_sentence[128];
  char content[100];
  int len;
  int space;
  unsigned char *p;
  u32 jitter;

  /* Update time */
  gps_sec++;
  if (gps_sec >= 60) {
    gps_sec = 0;
    gps_min++;
    if (gps_min >= 60) {
      gps_min = 0;
      gps_hour++;
      if (gps_hour >= 24)
        gps_hour = 0;
    }
  }

  /* Add jitter to fractional minutes
   * +/- small random amount to simulate noise
   */
  jitter = get_random_u32() % 20; /* 0..19 */
  if (get_random_u32() % 2)
    lat_min_frac += jitter;
  else
    lat_min_frac -= jitter;

  jitter = get_random_u32() % 20;
  if (get_random_u32() % 2)
    lon_min_frac += jitter;
  else
    lon_min_frac -= jitter;

  /* Constrain fractional part to reasonable bounds (0000-9999) mostly */
  if (lat_min_frac < 0)
    lat_min_frac = 0;
  if (lat_min_frac > 9999)
    lat_min_frac = 9999;
  if (lon_min_frac < 0)
    lon_min_frac = 0;
  if (lon_min_frac > 9999)
    lon_min_frac = 9999;

  /* Format content without $ and *CS */
  snprintf(
      content, sizeof(content),
      "GPGGA,%02d%02d%02d,%02d%02d.%04d,S,%03d%02d.%04d,E,1,08,0.9,545.4,M,"
      "46.9,M,,",
      gps_hour, gps_min, gps_sec, lat_deg, lat_min_int, lat_min_frac, lon_deg,
      lon_min_int, lon_min_frac);

  /* Calculate checksum */
  snprintf(nmea_sentence, sizeof(nmea_sentence), "$%s*%02X\r\n", content,
           nmea_checksum(content));

  len = strlen(nmea_sentence);

  tty = tty_port_tty_get(port);
  if (tty) {
    /* Push data to the TTY flip buffer */
    space = tty_prepare_flip_string(port, &p, len);
    if (space >= len) {
      memcpy(p, nmea_sentence, len);
      tty_flip_buffer_push(port);
    }
    tty_kref_put(tty);
  }

  /* Reschedule timer for 1Hz updates */
  mod_timer(&gps_timer, jiffies + msecs_to_jiffies(1000));
}

static int gps_tty_open(struct tty_struct *tty, struct file *file) {
  struct tty_port *port = &gps_tty_port;

  /*
   * In a real driver, we'd start hardware here.
   * For simulation, we ensure the timer is running.
   */
  return tty_port_open(port, tty, file);
}

static void gps_tty_close(struct tty_struct *tty, struct file *file) {
  struct tty_port *port = &gps_tty_port;
  tty_port_close(port, tty, file);
}

static ssize_t gps_tty_write(struct tty_struct *tty, const unsigned char *buf,
                             size_t count) {
  /*
   * We don't really do anything with simulation input,
   * but we should accept it to pretend we are a real device.
   */
  return count;
}

static unsigned int gps_tty_write_room(struct tty_struct *tty) {
  /* We have "infinite" room */
  return 255;
}

static const struct tty_operations gps_ops = {
    .open = gps_tty_open,
    .close = gps_tty_close,
    .write = gps_tty_write,
    .write_room = gps_tty_write_room,
};

static const struct tty_port_operations gps_port_ops = {};

static int __init gps_sim_init(void) {
  int retval;

  /* Allocate the tty driver */
  gps_tty_driver = tty_alloc_driver(GPS_TTY_MINORS, TTY_DRIVER_REAL_RAW |
                                                        TTY_DRIVER_DYNAMIC_DEV);
  if (IS_ERR(gps_tty_driver))
    return PTR_ERR(gps_tty_driver);

  /* Initialize the tty driver */
  gps_tty_driver->owner = THIS_MODULE;
  gps_tty_driver->driver_name = "gps_sim";
  gps_tty_driver->name = GPS_TTY_NAME;
  gps_tty_driver->major = GPS_TTY_MAJOR;
  gps_tty_driver->minor_start = 0;
  gps_tty_driver->type = TTY_DRIVER_TYPE_SERIAL;
  gps_tty_driver->subtype = SERIAL_TYPE_NORMAL;
  gps_tty_driver->init_termios = tty_std_termios;
  gps_tty_driver->init_termios.c_cflag = B9600 | CS8 | CREAD | HUPCL | CLOCAL;
  tty_set_operations(gps_tty_driver, &gps_ops);

  /* Initialize the tty port */
  tty_port_init(&gps_tty_port);
  gps_tty_port.ops = &gps_port_ops;
  /* Link port to driver so tty_port_open works */
  tty_port_link_device(&gps_tty_port, gps_tty_driver, 0);

  /* Register the tty driver */
  retval = tty_register_driver(gps_tty_driver);
  if (retval) {
    printk(KERN_ERR "gps-sim: failed to register tty driver\n");
    goto err_driver;
  }

  /* Register the device - this creates /dev/ttyGPS0 */
  tty_register_device(gps_tty_driver, 0, NULL);

  /* Setup the simulation timer */
  timer_setup(&gps_timer, gps_simulate_nmea, 0);
  mod_timer(&gps_timer, jiffies + msecs_to_jiffies(1000));

  printk(KERN_INFO "gps-sim: module loaded, device /dev/%s0 created\n",
         GPS_TTY_NAME);
  return 0;

err_driver:
  tty_port_destroy(&gps_tty_port);
  tty_driver_kref_put(gps_tty_driver);
  return retval;
}

static void __exit gps_sim_cleanup(void) {
#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 5, 0)
  timer_shutdown_sync(&gps_timer);
#else
  del_timer_sync(&gps_timer);
#endif

  tty_unregister_device(gps_tty_driver, 0);
  tty_unregister_driver(gps_tty_driver);
  tty_port_destroy(&gps_tty_port);
  tty_driver_kref_put(gps_tty_driver);

  printk(KERN_INFO "gps-sim: module unloaded\n");
}

module_init(gps_sim_init);
module_exit(gps_sim_cleanup);
