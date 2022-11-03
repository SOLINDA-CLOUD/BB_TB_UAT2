from odoo import _, api, fields, models

class ByProductDummy(models.Model):
    _name = 'by.product.dummy'
    _description = 'By Product Dummy'
    
    product_id = fields.Many2one('product.product', string='Product')
    product_uom_id = fields.Many2one('uom.uom', string='UoM')
    product_uom_qty = fields.Float(string='To Produce')
    colour = fields.Char('Color')
    size = fields.Char('Size')
    remarks = fields.Text('Remarks')
    mrp_id = fields.Many2one('mrp.production', string='MRP')
    fabric_po_id = fields.Many2one('data.fabric.lining', string='Fabric')
    lining_po_id = fields.Many2one('data.fabric.lining', string='Lining')

    @api.onchange('product_uom_qty')
    def _onchange_product_uom_qty(self):
        by_prod = self.env["stock.move"].search([('product_id', '=', self.product_id.id),('mrp_id', '=', self.mrp_id.id)],limit=1)
        if by_prod:
            by_prod.product_uom_qty = self.product_uom_qty
        else:
            self.mrp_id.product_qty = self.product_uom_qty
            

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    by_product_ids = fields.One2many('by.product.dummy', 'mrp_id', string='By Product')
    
    