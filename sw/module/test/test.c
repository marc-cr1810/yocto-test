#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Yocto Workspace");
MODULE_DESCRIPTION("A simple test kernel module");

static int __init test_init(void)
{
    printk(KERN_INFO "Hello from test module!\n");
    return 0;
}

static void __exit test_cleanup(void)
{
    printk(KERN_INFO "Goodbye from test module!\n");
}

module_init(test_init);
module_exit(test_cleanup);
