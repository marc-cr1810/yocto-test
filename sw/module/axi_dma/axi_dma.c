#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Yocto Workspace");
MODULE_DESCRIPTION("A simple axi_dma kernel module");

static int __init axi_dma_init(void)
{
    printk(KERN_INFO "Hello from axi_dma module!\n");
    return 0;
}

static void __exit axi_dma_cleanup(void)
{
    printk(KERN_INFO "Goodbye from axi_dma module!\n");
}

module_init(axi_dma_init);
module_exit(axi_dma_cleanup);
