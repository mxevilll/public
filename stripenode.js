const express = require('express');
const stripe = require('stripe')('sk_live_');
const bodyParser = require('body-parser');
const cors = require('cors');
const app = express();

app.use(bodyParser.json());

// Настройка CORS
app.use(cors({
  origin: ['http://localhost:3000', 'https://taronium.com'], // Указываем конкретные источники для CORS
  methods: ['GET', 'POST'], // Разрешаем методы
  allowedHeaders: ['Content-Type'],
  credentials: true // Разрешаем куки
}));

// Create PaymentIntent
app.post('/create-payment-intent', async (req, res) => {
  const { amount, currency, userId } = req.body;

  try {
    const paymentIntent = await stripe.paymentIntents.create({
      amount,
      currency,
      metadata: { userId },
      description: `Payment for userId: ${userId}`
    });

    res.send({
      clientSecret: paymentIntent.client_secret
    });
  } catch (error) {
    res.status(500).send({ error: error.message });
  }
});

// Endpoint for Stripe webhook
const endpointSecret = "";

app.post('/webhook', bodyParser.raw({ type: 'application/json' }), (request, response) => {
  const sig = request.headers['stripe-signature'];

  let event;

  try {
    event = stripe.webhooks.constructEvent(request.body, sig, endpointSecret);
  } catch (err) {
    console.log(`Webhook Error: ${err.message}`);
    return response.status(400).send(`Webhook Error: ${err.message}`);
  }

  if (event.type === 'payment_intent.succeeded') {
    const paymentIntent = event.data.object; // contains a Stripe PaymentIntent
    const userId = paymentIntent.metadata.userId; // Extract userId from metadata
    console.log(`PaymentIntent for ${paymentIntent.amount} was successful! UserId: ${userId}`);
    // Then define and call a function to handle the successful payment intent.
    handleSuccessfulPaymentIntent(paymentIntent);
  } else {
    console.log(`Unhandled event type ${event.type}`);
  }

  response.json({ received: true });
});

// Обработчик для создания сессии оформления заказа
app.post('/create-checkout-session', async (req, res) => {
  const { amount, currency, userId } = req.body;
  
  try {
    const session = await stripe.checkout.sessions.create({
      payment_method_types: ['card'],
      line_items: [{
        price_data: {
          currency: currency,
          product_data: {
            name: "Покупка на Taronium",
          },
          unit_amount: amount,
        },
        quantity: 1,
      }],
      metadata: { userId },
      mode: 'payment',
      success_url: `${req.headers.origin}/success?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${req.headers.origin}/cancel`,
    });

    res.json({ sessionId: session.id });
  } catch (error) {
    res.status(500).send({ error: error.message });
  }
});

// Helper function to handle successful PaymentIntent
function handleSuccessfulPaymentIntent(paymentIntent) {
  // Logic to handle successful payment intent
  console.log('Handle payment intent:', paymentIntent);
}

app.listen(3000, () => console.log('Node server listening on port 3000!'));
