flectra.define('show_order_pos.showOrder',function(require){
"use strict";

    var gui = require('point_of_sale.gui');
    var chrome = require('point_of_sale.chrome');
    var core = require('web.core');
    var models = require('point_of_sale.models');
    var PosModelSuper = models.PosModel;
    var pos_screens = require('point_of_sale.screens');
    var QWeb = core.qweb;
    var _t = core._t;

    models.load_models({
        model: 'pos.order',
        fields: ['id', 'name', 'session_id', 'state', 'pos_reference', 'partner_id', 'amount_total','lines', 'amount_tax', 
                'sequence_number', 'fiscal_position_id', 'pricelist_id', 'create_date', 'statement_ids'],
        domain: function(self){ return [['company_id','=',self.company.id]]; },
        loaded: function (self, pos_orders) {
            var orders = [];
            for (var i in pos_orders){
                orders[pos_orders[i].id] = pos_orders[i];
            }
            self.pos_orders = orders;
            self.order = [];
            for (var i in pos_orders){
                self.order[i] = pos_orders[i];
            }
        },
    });
 
    var ShowOrderButton = pos_screens.ActionButtonWidget.extend({
        template: 'ShowOrderButton',
        button_click: function(){
            if (this.pos.get_order().get_orderlines().length === 0){
                this.gui.show_screen('ShowOrdersWidget');
            }
            else{
                this.gui.show_popup('error',{
                    title :_t('Process Only one operation at a time'),
                    body  :_t('Process the current order first'),
                });
            }
        }
    });

    pos_screens.define_action_button({
        'name': 'Show Order',
        'widget': ShowOrderButton,
        'condition': function(){
            return this.pos;
        },
    });

    models.PosModel = models.PosModel.extend({
        _save_to_server: function (orders, options) {
            var result_new = PosModelSuper.prototype._save_to_server.call(this, orders, options);
            var self = this;
            var new_order = {};
            var orders_list = self.pos_orders;

            for (var i in orders) {
                var partners = self.partners;
                var partner = "";
                for(var j in partners){
                    if(partners[j].id == orders[i].data.partner_id){
                        partner = partners[j].name;
                    }
                }
                new_order = {
                    'amount_tax': orders[i].data.amount_tax,
                    'amount_total': orders[i].data.amount_total,
                    'pos_reference': orders[i].data.name,
                    'partner_id': [orders[i].data.partner_id, partner],
                    'session_id': [self.pos_session.id, self.pos_session.name]
                };
                orders_list.push(new_order);
                self.pos_orders = orders_list;
                self.gui.screen_instances.ShowOrdersWidget.render_list(orders_list);
            }
            return result_new;
        },
    });

    var ShowOrdersWidget = pos_screens.ScreenWidget.extend({
        template: 'ShowOrdersWidget',

        init: function(parent, options){
            this._super(parent, options);
            this.order_string = "";
        },
        auto_back: true,
        show: function(){
            var self = this;
            this._super();

            this.renderElement();
            this.$('.back').click(function(){
                self.gui.back();
            });
            var pos_orders = this.pos.pos_orders;
            this.render_list(pos_orders);

            var search_timeout = null;

            if(this.pos.config.iface_vkeyboard && this.chrome.widget.keyboard){
                this.chrome.widget.keyboard.connect(this.$('.searchbox input'));
            }

            this.$('.searchbox input').on('keyup',function(event){
                clearTimeout(search_timeout);
                var query = this.value;
                search_timeout = setTimeout(function(){
                    self.perform_search(query,event.which === 13);
                },70);
            });

            this.$('.searchbox .search-clear').click(function(){
                self.clear_search();
            });
        },
        perform_search: function(query, associate_result){
            var new_orders;
            if(query){
                new_orders = this.search_order(query);
                this.render_list(new_orders);
            }else{
                var orders = this.pos.pos_orders;
                this.render_list(orders);
            }
        },
        search_order: function(query){
            var self = this;
            try {
                query = query.replace(/[\[\]\(\)\+\*\?\.\-\!\&\^\$\|\~\_\{\}\:\,\\\/]/g,'.');
                query = query.replace(' ','.+');
                var re = RegExp("([0-9]+):.*?"+query,"gi");
            }catch(e){
                return [];
            }
            var results = [];
            for(var i = 0; i < self.pos.pos_orders.length; i++){
                var r = re.exec(this.order_string);
                if(r){
                    var id = Number(r[1]);
                    results.push(this.get_order_by_id(id));
                }else{
                    break;
                }
            }
            var uniqueresults = [];
            $.each(results, function(i, el){
                if($.inArray(el, uniqueresults) === -1) uniqueresults.push(el);
            });
            return uniqueresults;
        },
        // returns the order with the id provided
        get_order_by_id: function (id) {
            return this.pos.pos_orders[id];
        },
        clear_search: function(){
            var orders = this.pos.pos_orders;
            this.render_list(orders);
            this.$('.searchbox input')[0].value = '';
            this.$('.searchbox input').focus();
        },
        render_list: function(orders){
            var self = this;
            for(var i = 0, len = Math.min(orders.length,1000); i < len; i++) {
                if (orders[i]) {
                    var order = orders[i];
                    self.order_string += i + ':' + order.pos_reference + '\n';
                }
            }
            var contents = this.$el[0].querySelector('.show-order-list-lines');
            if (contents){
                contents.innerHTML = "";
                for(var i = 0, len = Math.min(orders.length,1000); i < len; i++) {
                    if (orders[i]) {
                        var order = orders[i];
                        var clientline_html = QWeb.render('ShowOrderLines', {widget: this, order: order});
                        var orderline = document.createElement('tbody');
                        orderline.innerHTML = clientline_html;
                        orderline = orderline.childNodes[1];
                        contents.appendChild(orderline);
                    }
                }
            }
        },
    });

    gui.define_screen({name:'ShowOrdersWidget', widget: ShowOrdersWidget});

    return {
        ShowOrdersWidget: ShowOrdersWidget
    }
});
