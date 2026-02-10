#include <linux/atomic.h>
#include <linux/cdev.h>
#include <linux/device.h>
#include <linux/fs.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/module.h>
#include <linux/slab.h>
#include <linux/timer.h>
#include <linux/uaccess.h>
#include <linux/wait.h>

#define DEVICE_NAME "pps_interrupt"
#define CLASS_NAME "pps_sim"

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Yocto Workspace");
MODULE_DESCRIPTION("A simple pps-sim kernel module");

static struct timer_list pps_timer;
static wait_queue_head_t pps_wait_queue;
static atomic_t pps_event_counter = ATOMIC_INIT(0);

static dev_t dev_num;
static struct cdev pps_cdev;
static struct class *pps_class = NULL;
static struct device *pps_device = NULL;

static void pps_timer_func(struct timer_list *t) {
  atomic_inc(&pps_event_counter);
  wake_up_interruptible(&pps_wait_queue);
  mod_timer(&pps_timer, jiffies + msecs_to_jiffies(1000));
}

static int pps_open(struct inode *inode, struct file *file) {
  int *last_seen_event;

  last_seen_event = kmalloc(sizeof(int), GFP_KERNEL);
  if (!last_seen_event)
    return -ENOMEM;

  /* Initialize with current counter so read blocks for the *next* event */
  *last_seen_event = atomic_read(&pps_event_counter);
  file->private_data = last_seen_event;
  return 0;
}

static int pps_release(struct inode *inode, struct file *file) {
  kfree(file->private_data);
  return 0;
}

static ssize_t pps_read(struct file *file, char __user *buf, size_t count,
                        loff_t *ppos) {
  int *last_seen_event = (int *)file->private_data;
  int current_event;
  char kbuf[32];
  int len;
  int ret;

  if (!last_seen_event)
    return -EFAULT;

  /* Wait until the global counter is greater than what we last saw */
  ret = wait_event_interruptible(
      pps_wait_queue,
      (current_event = atomic_read(&pps_event_counter)) > *last_seen_event);

  if (ret)
    return ret; /* Signal interrupted */

  len = snprintf(kbuf, sizeof(kbuf), "%d\n", current_event);
  if (len > count)
    len = count;

  if (copy_to_user(buf, kbuf, len))
    return -EFAULT;

  *last_seen_event = current_event;
  return len;
}

static const struct file_operations pps_fops = {
    .owner = THIS_MODULE,
    .open = pps_open,
    .release = pps_release,
    .read = pps_read,
};

static int __init pps_sim_init(void) {
  int ret;

  ret = alloc_chrdev_region(&dev_num, 0, 1, DEVICE_NAME);
  if (ret < 0) {
    printk(KERN_ALERT "pps-sim: Failed to allocate major number\n");
    return ret;
  }

  cdev_init(&pps_cdev, &pps_fops);
  pps_cdev.owner = THIS_MODULE;
  ret = cdev_add(&pps_cdev, dev_num, 1);
  if (ret < 0) {
    unregister_chrdev_region(dev_num, 1);
    printk(KERN_ALERT "pps-sim: Failed to add cdev\n");
    return ret;
  }

  pps_class = class_create(CLASS_NAME);
  if (IS_ERR(pps_class)) {
    cdev_del(&pps_cdev);
    unregister_chrdev_region(dev_num, 1);
    printk(KERN_ALERT "pps-sim: Failed to create class\n");
    return PTR_ERR(pps_class);
  }

  pps_device = device_create(pps_class, NULL, dev_num, NULL, DEVICE_NAME);
  if (IS_ERR(pps_device)) {
    class_destroy(pps_class);
    cdev_del(&pps_cdev);
    unregister_chrdev_region(dev_num, 1);
    printk(KERN_ALERT "pps-sim: Failed to create device\n");
    return PTR_ERR(pps_device);
  }

  init_waitqueue_head(&pps_wait_queue);
  timer_setup(&pps_timer, pps_timer_func, 0);

  ret = mod_timer(&pps_timer, jiffies + msecs_to_jiffies(1000));
  if (ret)
    printk(KERN_ERR "pps-sim: Error processing timer\n");

  printk(KERN_INFO "pps-sim: Module loaded, device /dev/%s created\n",
         DEVICE_NAME);
  return 0;
}

static void __exit pps_sim_cleanup(void) {
  del_timer_sync(&pps_timer);
  device_destroy(pps_class, dev_num);
  class_destroy(pps_class);
  cdev_del(&pps_cdev);
  unregister_chrdev_region(dev_num, 1);
  printk(KERN_INFO "pps-sim: Module unloaded\n");
}

module_init(pps_sim_init);
module_exit(pps_sim_cleanup);
