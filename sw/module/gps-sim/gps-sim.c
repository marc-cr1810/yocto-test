#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/serial.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/timer.h>
#include <linux/tty.h>
#include <linux/tty_driver.h>
#include <linux/tty_flip.h>
#include <linux/uaccess.h>

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

/*
 * We need a way to pass data to the tty layer.
 * In a real device, an interrupt would trigger this.
 * Here, we use a timer.
 */

static void gps_simulate_nmea(struct timer_list *t) {
  struct tty_struct *tty;
  struct tty_port *port = &gps_tty_port;
  char nmea_sentence[] =
      "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47\r\n";
  int len = strlen(nmea_sentence);
  int space;
  unsigned char *p;

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
  del_timer_sync(&gps_timer);

  tty_unregister_device(gps_tty_driver, 0);
  tty_unregister_driver(gps_tty_driver);
  tty_port_destroy(&gps_tty_port);
  tty_driver_kref_put(gps_tty_driver);

  printk(KERN_INFO "gps-sim: module unloaded\n");
}

module_init(gps_sim_init);
module_exit(gps_sim_cleanup);
