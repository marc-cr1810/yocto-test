#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
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

/* Module parameters for start location (in degrees * 1000000)
 * Example: -35.315075 -> -35315075
 */
static int start_lat = -35315075;
static int start_lon = 149129404;

module_param(start_lat, int, 0644);
MODULE_PARM_DESC(start_lat, "Starting Latitude in micro-degrees");
module_param(start_lon, int, 0644);
MODULE_PARM_DESC(start_lon, "Starting Longitude in micro-degrees");

static int error_rate = 0;
module_param(error_rate, int, 0644);
MODULE_PARM_DESC(error_rate, "Error rate (0-100%) for checksum corruption");

static int signal_loss = 0;
module_param(signal_loss, int, 0644);
MODULE_PARM_DESC(signal_loss, "Simulate signal loss (0=Good, 1=Lost)");

struct gps_sat {
  int prn;
  int elev;
  int az;
  int snr;
};

/* Virtual constellation */
static struct gps_sat sats[] = {
    {1, 45, 120, 30},  {3, 60, 210, 35}, {6, 30, 45, 25},   {9, 15, 300, 20},
    {12, 70, 180, 40}, {17, 25, 90, 28}, {22, 10, 270, 15}, {28, 50, 330, 32},
};
#define NUM_SATS (sizeof(sats) / sizeof(sats[0]))

static void update_coordinates_from_param(void) {
  int abs_lat, abs_lon;
  int min_part;

  abs_lat = (start_lat < 0) ? -start_lat : start_lat;
  lat_deg = abs_lat / 1000000;
  min_part = (abs_lat % 1000000) * 60;
  lat_min_int = min_part / 1000000;
  lat_min_frac = (min_part % 1000000) / 100; /* Keep 4 decimal places */

  abs_lon = (start_lon < 0) ? -start_lon : start_lon;
  lon_deg = abs_lon / 1000000;
  min_part = (abs_lon % 1000000) * 60;
  lon_min_int = min_part / 1000000;
  lon_min_frac = (min_part % 1000000) / 100;
}

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
  unsigned char cs;

  /* Re-calculate coordinates from parameters to support runtime updates */
  update_coordinates_from_param();

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

  /* Format GNGGA content */
  snprintf(
      content, sizeof(content),
      "GNGGA,%02d%02d%02d,%02d%02d.%04d,%c,%03d%02d.%04d,%c,1,08,0.9,545.4,"
      "M,46.9,M,,",
      gps_hour, gps_min, gps_sec, lat_deg, lat_min_int, lat_min_frac,
      (start_lat < 0) ? 'S' : 'N', lon_deg, lon_min_int, lon_min_frac,
      (start_lon < 0) ? 'W' : 'E');

  /* Handle Signal Loss */
  if (signal_loss) {
    /* Replace '1' (Fix valid) with '0' (Invalid) */
    /* GNGGA format: ... frac,N,deg,min,frac,E,1, ... */
    /* We know where the fix quality digit is relative to the end, but easier to
     * just regenerate with 0 if needed or modify string */
    /* Actually, let's just regenerate properly based on signal_loss */
    snprintf(
        content, sizeof(content),
        "GNGGA,%02d%02d%02d,%02d%02d.%04d,%c,%03d%02d.%04d,%c,%d,08,0.9,545.4,"
        "M,46.9,M,,",
        gps_hour, gps_min, gps_sec, lat_deg, lat_min_int, lat_min_frac,
        (start_lat < 0) ? 'S' : 'N', lon_deg, lon_min_int, lon_min_frac,
        (start_lon < 0) ? 'W' : 'E', (signal_loss ? 0 : 1));
  }

  /* Calculate checksum and format sentence */
  cs = nmea_checksum(content);
  if ((get_random_u32() % 100) < error_rate)
    cs++; /* Corrupt checksum */

  snprintf(nmea_sentence, sizeof(nmea_sentence), "$%s*%02X\r\n", content, cs);

  len = strlen(nmea_sentence);

  tty = tty_port_tty_get(port);
  if (tty) {
    /* Push GNGGA */
    space = tty_prepare_flip_string(port, &p, len);
    if (space >= len) {
      memcpy(p, nmea_sentence, len);
      tty_flip_buffer_push(port);
    }

    /* Format GNRMC content */
    /* $GNRMC,hhmmss.ss,A,ddmm.mmmm,N,dddmm.mmmm,E,speed,course,ddmmyy,,,mode*cs
     */
    /* Using dummy date 100226 (10th Feb 2026), dummy speed/course */
    snprintf(content, sizeof(content),
             "GNRMC,%02d%02d%02d,A,%02d%02d.%04d,%c,%03d%02d.%04d,%c,0.5,0.0,"
             "100226,,,A",
             gps_hour, gps_min, gps_sec, lat_deg, lat_min_int, lat_min_frac,
             (start_lat < 0) ? 'S' : 'N', lon_deg, lon_min_int, lon_min_frac,
             (start_lon < 0) ? 'W' : 'E');

    /* Handle Signal Loss for RMC */
    if (signal_loss) {
      /* Replace Status 'A' with 'V' */
      /* GNRMC,time,A,... */
      /* Regenerate for simplicity */
      snprintf(
          content, sizeof(content),
          "GNRMC,%02d%02d%02d,%c,%02d%02d.%04d,%c,%03d%02d.%04d,%c,0.5,0.0,"
          "100226,,,A",
          gps_hour, gps_min, gps_sec, (signal_loss ? 'V' : 'A'), lat_deg,
          lat_min_int, lat_min_frac, (start_lat < 0) ? 'S' : 'N', lon_deg,
          lon_min_int, lon_min_frac, (start_lon < 0) ? 'W' : 'E');
    }

    cs = nmea_checksum(content);
    if ((get_random_u32() % 100) < error_rate)
      cs++;

    snprintf(nmea_sentence, sizeof(nmea_sentence), "$%s*%02X\r\n", content, cs);
    len = strlen(nmea_sentence);

    /* Push GNRMC */
    space = tty_prepare_flip_string(port, &p, len);
    if (space >= len) {
      memcpy(p, nmea_sentence, len);
      tty_flip_buffer_push(port);
    }

    /* Format GNGSA content */
    /* $GNGSA,mode,fix_type,prn1...prn12,pdop,hdop,vdop*cs */
    /* Mode A (Auto), Fix 3 (3D), PRNs 1,3,6,12,17,28 (Active) */
    snprintf(content, sizeof(content),
             "GNGSA,A,%d,01,03,06,12,17,28,,,,,,,1.5,1.0,1.2",
             (signal_loss ? 1 : 3));

    cs = nmea_checksum(content);
    if ((get_random_u32() % 100) < error_rate)
      cs++;

    snprintf(nmea_sentence, sizeof(nmea_sentence), "$%s*%02X\r\n", content, cs);
    len = strlen(nmea_sentence);

    /* Push GNGSA */
    space = tty_prepare_flip_string(port, &p, len);
    if (space >= len) {
      memcpy(p, nmea_sentence, len);
      tty_flip_buffer_push(port);
    }

    /* Format GNGSV messages (2 messages for 8 sats) */
    /* $GNGSV,num_msgs,msg_num,num_sats,prn,elev,az,snr,...*cs */
    int msg;
    for (msg = 0; msg < 2; msg++) {
      int sat_start = msg * 4;
      /* Add some jitter to SNR */
      int snr0 = (sats[sat_start].snr + (get_random_u32() % 5)) *
                 (signal_loss ? 0 : 1);
      int snr1 = (sats[sat_start + 1].snr + (get_random_u32() % 5)) *
                 (signal_loss ? 0 : 1);
      int snr2 = (sats[sat_start + 2].snr + (get_random_u32() % 5)) *
                 (signal_loss ? 0 : 1);
      int snr3 = (sats[sat_start + 3].snr + (get_random_u32() % 5)) *
                 (signal_loss ? 0 : 1);

      snprintf(content, sizeof(content),
               "GNGSV,2,%d,08,%02d,%02d,%03d,%02d,%02d,%02d,%03d,%02d,%02d,%"
               "02d,%03d,%02d,%02d,%02d,%03d,%02d",
               msg + 1, sats[sat_start].prn, sats[sat_start].elev,
               sats[sat_start].az, snr0, sats[sat_start + 1].prn,
               sats[sat_start + 1].elev, sats[sat_start + 1].az, snr1,
               sats[sat_start + 2].prn, sats[sat_start + 2].elev,
               sats[sat_start + 2].az, snr2, sats[sat_start + 3].prn,
               sats[sat_start + 3].elev, sats[sat_start + 3].az, snr3);

      cs = nmea_checksum(content);
      if ((get_random_u32() % 100) < error_rate)
        cs++;

      snprintf(nmea_sentence, sizeof(nmea_sentence), "$%s*%02X\r\n", content,
               cs);
      len = strlen(nmea_sentence);

      /* Push GNGSV frame */
      space = tty_prepare_flip_string(port, &p, len);
      if (space >= len) {
        memcpy(p, nmea_sentence, len);
        tty_flip_buffer_push(port);
      }
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

  /* Initialize coordinates from module parameters */
  /* Initial update not strictly needed as loop does it, but good for
   * cleanliness */
  update_coordinates_from_param();

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
