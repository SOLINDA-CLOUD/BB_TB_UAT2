# Copyright 2017-19 Eficent Business and IT Consulting Services S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from dataclasses import field
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpProductionRequest(models.Model):
    _name = "mrp.production.request"
    _description = "Manufacturing Request"
    _inherit = "mail.thread"
    _order = "date_planned_start desc, id desc"

    @api.model
    def _get_default_requested_by(self):
        return self.env.user

    name = fields.Char(
        required=True,
        default='New',
        index=True,
        readonly=True,
    )

    trans_date = fields.Datetime(
        string='Transaction Date',
        default=fields.Datetime.now,
        index=True,
        required=True,
        states={"confirmed": [("readonly", False)]},
        )

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('mrp.production.request')
        return super(MrpProductionRequest, self).create(vals)

    origin = fields.Char(
        string="Source Document", readonly=True, states={"draft": [("readonly", False)]}
    )
    requested_by = fields.Many2one(
        comodel_name="res.users",
        string="Requested by",
        default=lambda self: self._get_default_requested_by(),
        required=True,
        track_visibility="onchange",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    assigned_to = fields.Many2one(
        comodel_name="res.users",
        string="Approver",
        track_visibility="onchange",
        readonly=True,
        states={"draft": [("readonly", False)]},
        domain=lambda self: [
            (
                "groups_id",
                "in",
                self.env.ref(
                    "mrp_production_request." "group_mrp_production_request_manager"
                ).id,
            )
        ],
    )
    description = fields.Text("Description")
    date_planned_start = fields.Datetime(
        "Deadline Start",
        copy=False,
        default=fields.Datetime.now,
        index=True,
        required=True,
        states={"confirmed": [("readonly", False)]},
    )
    date_planned_finished = fields.Datetime(
        "Deadline End",
        copy=False,
        default=fields.Datetime.now,
        index=True,
        states={"confirmed": [("readonly", False)]},
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    mrp_production_ids = fields.One2many(
        comodel_name="mrp.production",
        string="Manufacturing Orders",
        inverse_name="mrp_production_request_id",
        readonly=True,
    )
    mrp_production_count = fields.Integer(
        compute="_compute_mrp_production_count", string="MO's Count"
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("to_approve", "To Be Approved"),
            ("approved", "Approved"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        index=True,
        track_visibility="onchange",
        required=True,
        copy=False,
        default="draft",
    )
    procurement_group_id = fields.Many2one(
        string="Procurement Group", comodel_name="procurement.group", copy=False
    )
    propagate = fields.Boolean(
        "Propagate cancel and split",
        help="If checked, when the previous move of the move "
        "(which was generated by a next procurement) is cancelled "
        "or split, the move generated by this move will too",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
        domain=[("type", "in", ["product", "consu"])],
        track_visibility="onchange",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    product_tmpl_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        related="product_id.product_tmpl_id",
    )
    department = fields.Many2one('product.category', related='product_tmpl_id.categ_id', string='Department', store=True)

    image = fields.Image(string='Fabric Swatch')

    @api.onchange('product_id')
    def _onchange_image(self):
        if self.product_id:
            self.image = ''
            if self.product_id.image_1920:
                self.image = self.product_id.image_1920
            self.image = self.image

    original_size_id = fields.Many2one('original.sample', string='Original Sample')

    fit_notes = fields.Text(string='Fit Notes')
    product_qty = fields.Float(
        string="Required Quantity",
        required=False,
        track_visibility="onchange",
        digits="Product Unit of Measure",
        default=1.0,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        readonly=True,
        states={"draft": [("readonly", False)]},
        domain="[('category_id', '=', category_uom_id)]",
    )
    category_uom_id = fields.Many2one(related="product_uom_id.category_id")
    manufactured_qty = fields.Float(
        string="Quantity in Manufacturing Orders",
        compute="_compute_manufactured_qty",
        store=True,
        readonly=True,
        digits="Product Unit of Measure",
        help="Sum of the quantities in Manufacturing Orders (in any state).",
    )
    done_qty = fields.Float(
        string="Quantity Done",
        store=True,
        readonly=True,
        compute="_compute_manufactured_qty",
        digits="Product Unit of Measure",
        help="Sum of the quantities in all done Manufacturing Orders.",
    )
    pending_qty = fields.Float(
        string="Pending Quantity",
        compute="_compute_manufactured_qty",
        store=True,
        digits="Product Unit of Measure",
        readonly=True,
        help="Quantity pending to add to Manufacturing Orders "
        "to fulfill the Manufacturing Request requirement.",
    )
    bom_id = fields.Many2one(
        comodel_name="mrp.bom",
        string="Bill of Materials",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    routing_id = fields.Many2one(
        comodel_name="mrp.routing",
        string="Routing",
        on_delete="setnull",
        readonly=True,
        states={"draft": [("readonly", False)]},
        help="The list of operations (list of work centers) to produce "
        "the finished product. The routing is mainly used to compute "
        "work center costs during operations and to plan future loads "
        "on work centers based on production plannification.",
    )
    location_src_id = fields.Many2one(
        comodel_name="stock.location",
        string="Raw Materials Location",
        default=lambda self: self.env["stock.location"].browse(
            self.env["mrp.production"]._get_default_location_src_id()
        ),
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    location_dest_id = fields.Many2one(
        comodel_name="stock.location",
        string="Finished Products Location",
        default=lambda self: self.env["stock.location"].browse(
            self.env["mrp.production"]._get_default_location_dest_id()
        ),
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    picking_type_id = fields.Many2one(
        comodel_name="stock.picking.type",
        string="Picking Type",
        default=lambda self: self.env["stock.picking.type"].browse(
            self.env["mrp.production"]._get_default_picking_type()
        ),
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    move_dest_ids = fields.One2many(
        comodel_name="stock.move",
        inverse_name="created_mrp_production_request_id",
        string="Stock Movements of Produced Goods",
    )
    orderpoint_id = fields.Many2one(
        comodel_name="stock.warehouse.orderpoint", string="Orderpoint"
    )

    # Notes
    label_placement = fields.Char(string='Label Placement')
    hanger_tape = fields.Char(string='Hanger Tape')
    seams = fields.Char(string='Seams')
    hem = fields.Char(string='Hem')
    zip_position = fields.Char(string='Zip Position')
    button_position = fields.Char(string='Button Position')
    mesh_tape = fields.Char(string='Mesh Tape')
    facing = fields.Char(string='Facing')
    special_trim = fields.Char(string='Special Trim')
    fabric_qty = fields.Integer(string='Fabric Qty')
    consumptions = fields.Char(string='Consumptions')
    cutting_time = fields.Date(string='Cutting Time')
    make_time = fields.Date(string='Make Time')
    make_cost = fields.Float(string='Make Cost')
    
    _sql_constraints = [
        (
            "name_uniq",
            "unique(name, company_id)",
            "Reference must be unique per Company!",
        )
    ]

    @api.model
    def _get_mo_valid_states(self):
        return ["planned", "confirmed", "progress", "done"]

    @api.depends("mrp_production_ids", "mrp_production_ids.state", "state")
    def _compute_manufactured_qty(self):
        valid_states = self._get_mo_valid_states()
        for req in self:
            done_mo = req.mrp_production_ids.filtered(
                lambda mo: mo.state in "done"
            ).mapped("product_qty")
            req.done_qty = sum(done_mo)
            valid_mo = req.mrp_production_ids.filtered(
                lambda mo: mo.state in valid_states
            ).mapped("product_qty")
            req.manufactured_qty = sum(valid_mo)
            req.pending_qty = max(req.product_qty - req.manufactured_qty, 0.0)

    def _compute_mrp_production_count(self):
        for rec in self:
            rec.mrp_production_count = len(rec.mrp_production_ids)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            self.bom_id = self.env["mrp.bom"]._bom_find(
                products = self.product_id,
                company_id=self.company_id.id,
                picking_type=self.picking_type_id,
            )['id']

    def _subscribe_assigned_user(self, vals):
        self.ensure_one()
        if vals.get("assigned_to"):
            self.message_subscribe(
                partner_ids=self.assigned_to.mapped("partner_id").ids
            )

    @api.model
    def _create_sequence(self, vals):
        if not vals.get("name") or vals.get("name") == "/":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("mrp.production.request") or "/"
            )
        return vals

    @api.model
    def create(self, vals):
        """Add sequence if name is not defined and subscribe to the thread
        the user assigned to the request."""
        vals = self._create_sequence(vals)
        res = super().create(vals)
        res._subscribe_assigned_user(vals)
        return res

    def write(self, vals):
        res = super().write(vals)
        for request in self:
            request._subscribe_assigned_user(vals)
        return res

    def button_to_approve(self):
        self.write({"state": "to_approve"})
        return True

    def button_approved(self):
        self.write({"state": "approved"})
        return True

    def button_done(self):
        self.write({"state": "done"})
        return True

    def _check_reset_allowed(self):
        if any(
            [
                s in self._get_mo_valid_states()
                for s in self.mapped("mrp_production_ids.state")
            ]
        ):
            raise UserError(
                _(
                    "You cannot reset a manufacturing request if the related "
                    "manufacturing orders are not cancelled."
                )
            )

    def button_draft(self):
        self._check_reset_allowed()
        self.write({"state": "draft"})
        return True

    def _check_cancel_allowed(self):
        if any([s == "done" for s in self.mapped("state")]):
            raise UserError(
                _(
                    "You cannot reject a manufacturing request related to "
                    "done procurement orders."
                )
            )

    def button_cancel(self):
        self._check_cancel_allowed()
        self.write({"state": "cancel"})
        self.mapped("move_dest_ids").filtered(
            lambda r: r.state != "cancel"
        )._action_cancel()
        return True

    def action_view_mrp_productions(self):
        action = self.env.ref("mrp.mrp_production_action")
        result = action.read()[0]
        result["context"] = {}
        mos = self.mapped("mrp_production_ids")
        # choose the view_mode accordingly
        if len(mos) != 1:
            result["domain"] = [("id", "in", mos.ids)]
        elif len(mos) == 1:
            form = self.env.ref("mrp.mrp_production_form_view", False)
            result["views"] = [(form and form.id or False, "form")]
            result["res_id"] = mos[0].id
        return result

class OriginalSample(models.Model):
    _name = 'original.sample'
    _description = 'Original Sample'

    name = fields.Char(string='Name')
    sample_size = fields.Integer(string='Sample Size')
    approved_size = fields.Integer(string='Sample is Approved Size')
    make_size = fields.Integer(string='Please make Sample in Size')