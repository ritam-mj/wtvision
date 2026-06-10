import prisma from './config/db.js';

async function main() {
  console.log('🌱 Starting database seeding...');

  // 1. Power Tools Category
  const powerTools = await prisma.itemCategory.upsert({
    where: { name: 'Power Tools' },
    update: {},
    create: {
      name: 'Power Tools',
      icon: 'Hammer',
      schema: [
        { field_name: 'brand', type: 'string', required: true },
        { field_name: 'power_source', type: 'string', required: true },
        { field_name: 'voltage_volts', type: 'number', required: false },
      ],
    },
  });
  console.log(`✅ Upserted category: ${powerTools.name}`);

  // 2. SaaS Memberships Category (Digital credential example)
  const saas = await prisma.itemCategory.upsert({
    where: { name: 'SaaS Memberships' },
    update: {},
    create: {
      name: 'SaaS Memberships',
      icon: 'Key',
      schema: [
        { field_name: 'platform_name', type: 'string', required: true },
        { field_name: 'membership_tier', type: 'string', required: true },
      ],
    },
  });
  console.log(`✅ Upserted category: ${saas.name}`);

  // 3. Camping Gear Category
  const camping = await prisma.itemCategory.upsert({
    where: { name: 'Camping Gear' },
    update: {},
    create: {
      name: 'Camping Gear',
      icon: 'Tent',
      schema: [
        { field_name: 'brand', type: 'string', required: true },
        { field_name: 'capacity_persons', type: 'number', required: false },
        { field_name: 'weatherproof_rating', type: 'string', required: false },
      ],
    },
  });
  console.log(`✅ Upserted category: ${camping.name}`);

  console.log('🌿 Seeding completed successfully!');
}

main()
  .catch((e) => {
    console.error('❌ Seeding failed:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
