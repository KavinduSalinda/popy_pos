import type { Locale } from '@/i18n/languages';
import { SI_HANDBOOK_SECTIONS } from './content.si';

export interface HandbookParameter {
  name: string;
  required: boolean;
  details: string;
}

export interface HandbookOperation {
  title: string;
  who: string;
  path: string;
  steps: string[];
  parameters?: HandbookParameter[];
  notes?: string[];
}

export interface HandbookTopic {
  title: string;
  body: string;
}

export interface HandbookSection {
  id: string;
  title: string;
  summary: string;
  notes?: string[];
  operations?: HandbookOperation[];
  topics?: HandbookTopic[];
}

const productFields: HandbookParameter[] = [
  {
    name: 'Name',
    required: true,
    details: 'The name staff and customers see. Up to 120 characters.',
  },
  {
    name: 'SKU',
    required: true,
    details:
      'Stock-keeping code. Required, unique in this shop, up to 60 characters.',
  },
  {
    name: 'Barcode',
    required: false,
    details:
      'Optional scan code, unique in this shop when set, up to 60 characters. Type it, scan it, or use Generate. Print a label from the form or from the product row.',
  },
  {
    name: 'Category',
    required: true,
    details:
      'Required. Pick a category that already exists in this shop. Add one under Categories first if the list is empty.',
  },
  {
    name: 'Brand',
    required: false,
    details: 'Optional. Up to 80 characters.',
  },
  {
    name: 'Unit',
    required: true,
    details:
      'How the item is counted: pcs, kg, g, litre, ml, box, pack, or dozen. At the point of sale, kg, g, litre, and ml can be sold in fractions (up to 3 decimal places, minimum 0.001). Other units sell as whole numbers.',
  },
  {
    name: 'Cost price',
    required: true,
    details:
      'Last known cost. Use 0 or more. Receiving a purchase overwrites this with that line’s cost.',
  },
  {
    name: 'Selling price',
    required: true,
    details:
      'The price used at the point of sale. Use 0 or more.',
  },
  {
    name: 'Reorder level',
    required: true,
    details:
      'Whole number, 0 or more. The product is low stock when quantity is above 0 and at or below this number. 0 means no low-stock alert.',
  },
  {
    name: 'Stock quantity',
    required: true,
    details:
      'Amount on hand. 0 or more, up to 3 decimal places. On a new product, a number above 0 is recorded as opening stock. On edit, the difference from the current on-hand amount is added or removed. The result cannot go below 0.',
  },
  {
    name: 'Active',
    required: true,
    details:
      'On by default. Active products appear on the point of sale. Turning this off hides the product from the point of sale and from the Products list.',
  },
];

export const HANDBOOK_SECTIONS: HandbookSection[] = [
  {
    id: 'how-it-works',
    title: 'How the shop works',
    summary:
      'Products, stock, sales, and people belong to the shop you are working in. Nothing is shared with another shop.',
    notes: [
      'Super Admin can switch shops from the top bar. Other staff stay in the shop they are assigned to.',
      'Set the on-hand quantity on the product form when you create or edit a product. Quantity also changes when you sell, receive a purchase, adjust inventory, or record a return.',
      'Super Admin and Manager run the shop. A Cashier sells and can look up products, customers, and sales. An Inventory Officer updates products, stock, and purchases, and does not use the point of sale.',
    ],
  },
  {
    id: 'products',
    title: 'Products',
    summary:
      'The Products screen is the catalog: name, prices, unit, on-hand quantity, and whether the item can be sold.',
    operations: [
      {
        title: 'Add a product',
        who: 'Super Admin and Manager. Cashiers can view the list. Inventory Officers can edit products, not create them.',
        path: 'Products → New product',
        steps: [
          'Open Products in the sidebar.',
          'Choose New product.',
          'Fill in the fields below. Barcode and brand can be left blank. Stock quantity is the amount on hand now. Use 0 if nothing is on the shelf yet.',
          'Choose Create. If stock quantity is above 0, that amount is saved as opening stock.',
          'You can still change stock later from Purchases or Inventory.',
        ],
        parameters: productFields,
        notes: [
          'Search the list by name, SKU, or barcode, and filter by category.',
          'The list shows active products only.',
        ],
      },
      {
        title: 'Update a product',
        who: 'Super Admin, Manager, and Inventory Officer.',
        path: 'Products → Edit on the row',
        steps: [
          'Open Products and find the product.',
          'Choose Edit.',
          'Change the fields and choose Save changes.',
          'Change Stock quantity if the amount on hand should be different. The difference is added or removed. The result cannot go below 0.',
        ],
        parameters: productFields,
        notes: [
          'Turning Active off hides the product from this list and from the point of sale. This list has no way to show inactive products, so switch Active off only when the item should leave the catalog.',
        ],
      },
      {
        title: 'Delete a product',
        who: 'Super Admin and Manager.',
        path: 'Products → Delete on the row',
        steps: [
          'Open Products and choose Delete on the row.',
          'Confirm Delete product.',
          'If the product has never been used on a sale or a purchase, it is removed.',
          'If it has been used on a sale or a purchase, it is deactivated instead. It leaves the Products list and the point of sale, and past sales stay intact.',
        ],
      },
    ],
  },
  {
    id: 'stock',
    title: 'Adding stock',
    summary:
      'Add stock by receiving a purchase, or correct it with an inventory adjustment. Both are limited to Super Admin, Manager, and Inventory Officer.',
    notes: [
      'Out of stock means quantity is 0 or below.',
      'Low stock means quantity is above 0 and at or below the reorder level. A reorder level of 0 does not raise a low-stock alert.',
      'In stock means quantity is above the reorder level.',
    ],
    operations: [
      {
        title: 'Receive stock with a purchase',
        who: 'Super Admin, Manager, and Inventory Officer.',
        path: 'Purchases → New purchase, or open an ordered purchase → Receive goods',
        steps: [
          'Open Purchases and choose New purchase.',
          'Pick a supplier and add at least one product line.',
          'Set the status. Draft saves the order and does not change stock. Ordered means it is awaiting delivery and does not change stock. Received adds each line’s quantity now and sets that product’s cost price to the line cost.',
          'The form starts as Ordered. Leave it there if the goods have not arrived yet.',
          'When an ordered delivery arrives, open the purchase and choose Receive goods. Stock increases, cost prices update, and the purchase becomes Received.',
          'Cancel order is available only while the purchase is Ordered. Cancelling does not change stock.',
          'You can edit a draft or ordered purchase. Editing does not change stock.',
          'You can delete a draft, ordered, or cancelled purchase. A received purchase cannot be deleted. Deleting an unreceived purchase does not change stock.',
        ],
        parameters: [
          {
            name: 'Supplier',
            required: true,
            details: 'A supplier already saved in this shop.',
          },
          {
            name: 'Status',
            required: false,
            details:
              'Draft, Ordered, or Received. If you do not change it, the purchase is Ordered and stock stays the same until you receive it.',
          },
          {
            name: 'Note',
            required: false,
            details: 'Optional. Up to 255 characters.',
          },
          {
            name: 'Product',
            required: true,
            details:
              'At least one line. Each line is a product in this shop.',
          },
          {
            name: 'Qty',
            required: true,
            details:
              'Whole number, at least 1, even when the product unit is kg or litre.',
          },
          {
            name: 'Cost',
            required: true,
            details:
              '0 or more. When the purchase is received, this becomes the product’s cost price.',
          },
        ],
        notes: [
          'A received purchase is numbered like PO-2026-0001. Copy that reference if you later return the goods.',
        ],
      },
      {
        title: 'Adjust stock',
        who: 'Super Admin, Manager, and Inventory Officer.',
        path: 'Inventory → New adjustment, or click a product row',
        steps: [
          'Open Inventory. Use the tabs to see everything, movements, low stock, or out of stock.',
          'Choose New adjustment, or click a product if you are allowed to adjust it.',
          'Pick the product and a type.',
          'Enter a quantity greater than 0, or type the New total you want on hand. The other field updates to match.',
          'Damage, Loss, and Expire remove that quantity. Found and Add add it.',
          'Choose Save adjustment. The result cannot go below zero. If it would, the adjustment is rejected.',
        ],
        parameters: [
          {
            name: 'Product',
            required: true,
            details: 'A product in this shop.',
          },
          {
            name: 'Adjustment type',
            required: true,
            details:
              'Damage, Loss, and Expire remove stock. Found and Add increase stock.',
          },
          {
            name: 'Quantity',
            required: true,
            details:
              'A number greater than 0, up to 3 decimal places. Damage, Loss, and Expire remove this amount. Found and Add add it.',
          },
          {
            name: 'New total',
            required: true,
            details:
              'The on-hand count after the adjustment. Changing the type or quantity updates this. Typing a new total updates the quantity to the difference. Damage, Loss, and Expire cannot raise the total. Found and Add cannot lower it. The result cannot go below 0.',
          },
          {
            name: 'Note',
            required: false,
            details: 'Optional. Up to 255 characters.',
          },
        ],
      },
    ],
  },
  {
    id: 'selling',
    title: 'Selling',
    summary:
      'Sell active products from Point of Sale. Use Sales afterward to find the receipt reference you need for a return.',
    operations: [
      {
        title: 'Sell at the point of sale',
        who: 'Super Admin, Manager, and Cashier. Inventory Officers do not sell.',
        path: 'Point of Sale',
        steps: [
          'Open Point of Sale.',
          'Add active products by clicking them, searching, or scanning a barcode.',
          'Set each quantity. It cannot be higher than the on-hand stock. kg, g, litre, and ml can use fractions (minimum 0.001, up to 3 decimal places). Other units are whole numbers.',
          'Optionally attach a customer. The discount is a flat amount and cannot be more than the subtotal. Tax is added on the amount after the discount.',
          'Take payment: Cash, Card, Mobile, or Credit. Cash asks how much was paid. The other methods record the sale total as paid.',
          'The sale is saved with a reference such as SL-2026-0001, and each line reduces on-hand stock.',
          'A completed sale cannot be edited or deleted. Use Returns if the customer brings the goods back.',
        ],
        parameters: [
          {
            name: 'Product',
            required: true,
            details: 'Must be active and in this shop.',
          },
          {
            name: 'Quantity',
            required: true,
            details:
              'Cannot exceed on-hand stock. Fractions are allowed only for kg, g, litre, and ml.',
          },
          {
            name: 'Customer',
            required: false,
            details:
              'Optional. A sale with no customer is shown as Walk-in in Sales.',
          },
          {
            name: 'Discount',
            required: false,
            details: 'Optional flat amount, not more than the subtotal.',
          },
          {
            name: 'Payment method',
            required: true,
            details: 'Cash, Card, Mobile, or Credit.',
          },
          {
            name: 'Amount paid',
            required: false,
            details:
              'Shown for cash, so you can record what the customer handed over and see the change. Card, Mobile, and Credit record the sale total as paid.',
          },
        ],
        notes: [
          'Checkout can be completed offline. The receipt uses an OFF- reference until the sale syncs. Stock adjustments, purchases, and returns need a connection.',
        ],
      },
      {
        title: 'Find a receipt',
        who: 'Super Admin, Manager, and Cashier.',
        path: 'Sales',
        steps: [
          'Open Sales.',
          'Search by the receipt reference or the customer name.',
          'Open the row and copy the SL- reference. You will paste it into a sales return.',
        ],
        parameters: [
          {
            name: 'Search',
            required: false,
            details: 'Receipt reference, such as SL-2026-0001, or the customer name.',
          },
        ],
      },
    ],
  },
  {
    id: 'returns',
    title: 'Returns',
    summary:
      'Return a sale from a bill reference, a barcode, or a SKU. A purchase return still uses the purchase reference.',
    operations: [
      {
        title: 'Return a sale',
        who: 'Super Admin, Manager, and Inventory Officer. Cashiers can look up the receipt, but they cannot record the return.',
        path: 'Returns → Sales Return',
        steps: [
          'Open Returns and stay on Sales Return.',
          'Enter a bill reference (SL- or the numeric sale id), a barcode, or a SKU, then choose Find.',
          'A bill returns whatever quantity is still left on that receipt. A barcode or SKU returns that product from the newest sale that still has some left. The form shows the sale reference, the quantity left, and a suggested refund.',
          'For a product, change the quantity if you are not returning 1. Enter a reason, adjust the refund if you need to, and choose Process sales return.',
          'Only the returned quantity is added back to stock. The original sale total, payment method, and loyalty points stay unchanged.',
        ],
        parameters: [
          {
            name: 'Bill, barcode, or SKU',
            required: true,
            details:
              'An SL- reference, such as SL-2026-0060, or the numeric sale id. A barcode or SKU must belong to this shop, including an inactive product. When the same text is both a bill and a SKU, the bill is used.',
          },
          {
            name: 'Quantity',
            required: false,
            details:
              'Shown for a barcode or SKU. Defaults to 1 when at least 1 remains, otherwise the remaining fraction. It cannot exceed what is left on the matched sale.',
          },
          {
            name: 'Reason',
            required: true,
            details: 'Why the goods came back. Up to 255 characters.',
          },
          {
            name: 'Refund amount',
            required: true,
            details:
              'The amount you are handing back, 0 or more. It starts at the line value after the sale discount, and the server caps it at the money still left on that sale. It does not change the original receipt.',
          },
        ],
        notes: [
          'A barcode or SKU attaches to the newest returnable sale without asking. Type the bill reference when the item came from an older receipt.',
          'Recording a bill that has already been fully returned does not add the quantities back again.',
        ],
      },
      {
        title: 'Return a purchase',
        who: 'Super Admin, Manager, and Inventory Officer.',
        path: 'Returns → Purchase Return, or open a received purchase → Return',
        steps: [
          'Return goods only after the purchase has been received.',
          'From Returns, open Purchase Return and enter the PO- reference, a reason, and the return amount. Or open the received purchase and choose Return. That dialog starts the amount at the purchase total.',
          'Choose Process purchase return.',
          'The full order quantity is taken back out of stock.',
        ],
        parameters: [
          {
            name: 'Purchase reference',
            required: true,
            details:
              'The PO- reference from Purchases, for example PO-2026-0001. A numeric purchase id also works.',
          },
          {
            name: 'Reason',
            required: true,
            details: 'Why the goods are going back. Up to 255 characters.',
          },
          {
            name: 'Return amount',
            required: true,
            details:
              'The amount to record, 0 or more. It is stored as you enter it. It is not calculated from the lines.',
          },
        ],
        notes: [
          'If one line does not have enough stock to remove, that line is skipped and the return is still saved. Check Inventory afterward if the quantities do not look right.',
        ],
      },
    ],
  },
  {
    id: 'also',
    title: 'Also in the app',
    summary:
      'The rest of the sidebar, in short. Stock still moves only through sales, purchases, adjustments, and returns.',
    topics: [
      {
        title: 'Categories',
        body: 'Name is required (up to 80 characters, unique in the shop). Description is optional. A category cannot be deleted while products still use it.',
      },
      {
        title: 'Customers',
        body: 'Name and phone are stored for the shop; phone is unique here. Email and address are optional. Loyalty points are edited by hand. Selling and returns do not change them. Cashiers can manage customers.',
      },
      {
        title: 'Suppliers',
        body: 'Name is required. Company, phone, email, and address are optional, and phone is unique in the shop. Inventory Officers can view suppliers. Super Admin and Manager create and update them.',
      },
      {
        title: 'Users',
        body: 'Super Admin and Manager manage staff: name, email, role, active, and a password of at least 6 characters (required when creating someone). A manager cannot assign Super Admin. You cannot delete your own account.',
      },
      {
        title: 'Attendance',
        body: 'Pro shops on the cloud, and every shop on the desktop app. Manager, Cashier, and Inventory Officer clock in and out once each per day. Super Admin can view the sheet and does not mark attendance.',
      },
      {
        title: 'Settings',
        body: 'Email and SMS run on the cloud version, and only for a Pro shop. Switches cover checkout receipts, whether cashiers may send them, low-stock alerts, and messages for a new customer or a new user. The desktop app does not send email or SMS.',
      },
      {
        title: 'Insights',
        body: 'The requirements report estimates units to buy for 7, 30, and 90 days from the last 30 days of sales. A written forecast and questions use a free Groq key saved for this shop.',
      },
      {
        title: 'Offline checkout',
        body: 'The point of sale catalog, customers, and checkout work offline and sync later. Adjustments, purchases, returns, the dashboard, and settings need a connection.',
      },
    ],
  },
];

export interface HandbookUi {
  title: string;
  subtitle: string;
  nav: string;
  sections: string;
  who: string;
  where: string;
  steps: string;
  parameters: string;
  goodToKnow: string;
  field: string;
  required: string;
  optional: string;
  whatItDoes: string;
}

export const HANDBOOK_UI: Record<Locale, HandbookUi> = {
  en: {
    title: 'Handbook',
    subtitle: 'How to run the shop: products, stock, sales, and returns.',
    nav: 'Handbook',
    sections: 'Handbook sections',
    who: 'Who',
    where: 'Where',
    steps: 'Steps',
    parameters: 'Parameters',
    goodToKnow: 'Good to know',
    field: 'Field',
    required: 'Required',
    optional: 'Optional',
    whatItDoes: 'What it does',
  },
  si: {
    title: 'අත්පොත',
    subtitle: 'කඩේ වැඩේ කරන විදිහ: භාණ්ඩ, තොග, විකුණුම්, ආපසු භාරගැනීම්.',
    nav: 'අත්පොත',
    sections: 'අත්පොතේ කොටස්',
    who: 'කාටද පුළුවන්',
    where: 'කොහෙන්ද',
    steps: 'පියවර',
    parameters: 'පුරවන තොරතුරු',
    goodToKnow: 'මතක තියාගන්න',
    field: 'කොටුව',
    required: 'අනිවාර්යයි',
    optional: 'අනිවාර්ය නැහැ',
    whatItDoes: 'මොකද වෙන්නේ',
  },
};

export const SINHALA_FONT =
  "'Noto Sans Sinhala', 'Iskoola Pota', 'Nirmala UI', sans-serif";

export const getHandbookSections = (locale: Locale): HandbookSection[] =>
  locale === 'si' ? SI_HANDBOOK_SECTIONS : HANDBOOK_SECTIONS;
